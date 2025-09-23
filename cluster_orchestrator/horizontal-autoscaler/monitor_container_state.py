import time
import os
import threading
from threading import Thread, Event, Lock
from other_requests import is_cluster_full
from horizontal_autoscaler_db import delete_scaling_config, get_scaling_config, set_scaling_config

COOLDOWN_SECONDS = os.environ.get("COOLDOWN_SECONDS", 30)

class ServiceScaler:
    """
    This class is responsible for monitoring the state of a service and scaling it up or down based on the state of the service.
    It is a singleton class and is used to monitor multiple services.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, get_service_metrics=None, scale_service_to_count=None, scale_up_service_by_cluster=None):
        """Ensure a single instance (Singleton Pattern)"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ServiceScaler, cls).__new__(cls)
        return cls._instance


    def __init__(self, get_service_metrics=None, scale_service_to_count=None, scale_up_service_by_cluster=None):
        """Initialize only once"""
        # Initialize _initialized first before checking it
        if not hasattr(self, '_initialized'):
            self._initialized = False

        if self._initialized:
            return

        self._initialized = True
        self.get_service_metrics = get_service_metrics
        self.scale_service_to_count = scale_service_to_count
        self.scale_up_service_by_cluster = scale_up_service_by_cluster
        self.running_threads = {}
        self.stop_events = {}
        self.initial_replicas = {}
        self.last_scale_down_time = {}
        self.data_lock = Lock()

    def monitor_single_service(self, service_id, cluster_id):
        """Monitor a single service"""
        print(f"Monitoring with Thread {threading.current_thread().name} service {service_id}")
        try:
            scaling_config = get_scaling_config(service_id)
            if not scaling_config:
                print(f"No scaling config found for service {service_id}")
                return

            metrics = self.get_service_metrics(service_id)
            if not metrics:
                print(f"Failed to get metrics for service {service_id}, skipping monitoring cycle.")
                return

            print(metrics)

            avg_cpu = sum(metrics["cpu_per_container"]) / len(metrics["cpu_per_container"])
            avg_ram = sum(metrics["ram_per_container"]) / len(metrics["ram_per_container"])
            overloaded = avg_cpu > scaling_config["cpu_threshold"] or avg_ram > scaling_config["ram_threshold"]

            current_replicas = metrics["replica_count"]

            with self.data_lock:
                if service_id not in self.initial_replicas:
                    self.initial_replicas[service_id] = current_replicas
                initial_replicas = self.initial_replicas[service_id]

            # Scale Up
            if overloaded and current_replicas < scaling_config["max_replicas"]:
                new_replica_count = min(scaling_config["max_replicas"], current_replicas + 1)
                if is_cluster_full(cluster_id):
                    self.scale_service_to_count(service_id, new_replica_count, current_replicas)
                else:
                    self.scale_up_service_by_cluster(service_id, cluster_id)

            # Scale Down
            elif not overloaded and current_replicas > scaling_config["min_replicas"]:
                with self.data_lock:
                    last_time = self.last_scale_down_time.get(service_id, 0)

                if (time.time() - last_time) > COOLDOWN_SECONDS:
                    with self.data_lock:
                        self.last_scale_down_time[service_id] = time.time()
                    new_replica_count = max(scaling_config["min_replicas"], current_replicas - 1)
                    self.scale_service_to_count(service_id, new_replica_count, current_replicas)

        except Exception as e:
            print(f"Error monitoring service {service_id}: {e}")

    def start_monitoring_services(self, service_id, scaling_config, check_interval, cluster_id):
        """Start monitoring a service"""
        with self.data_lock:
            if service_id in self.running_threads:
                print(f"Service {service_id} is already being monitored.")
                return

            set_scaling_config(service_id, {**scaling_config, "cluster_id": cluster_id})

            stop_event = Event()
            self.stop_events[service_id] = stop_event

        def monitor_loop():
            while not stop_event.is_set():
                self.monitor_single_service(service_id, cluster_id)
                time.sleep(int(check_interval))

        monitor_thread = Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        with self.data_lock:
            self.running_threads[service_id] = monitor_thread
        print(f"Started monitoring service {service_id}")

    def stop_monitoring_service(self, service_id):
        """Stop monitoring a service"""
        with self.data_lock:
            if service_id in self.stop_events:
                self.stop_events[service_id].set()
                self.running_threads.pop(service_id, None)
                self.stop_events.pop(service_id, None)
                delete_scaling_config(service_id)
                print(f"Stopped monitoring service {service_id}")
            else:
                print(f"Service {service_id} is not being monitored.")
