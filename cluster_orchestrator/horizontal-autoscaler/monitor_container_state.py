import time
from threading import Thread, Event, Lock
from other_requests import is_cluster_full

class ServiceScaler:
    """
    This class is responsible for monitoring the state of a service and scaling it up or down based on the metrics.
    """
    _instance = None
    _lock = Lock()

    def __new__(cls, get_service_metrics=None, scale_service_to_count=None, scale_up_service_by_cluster=None):
        """Ensure a single instance (Singleton Pattern)"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ServiceScaler, cls).__new__(cls)
                cls._instance._initialized = False  # Ensure __init__ runs once
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
        self.initial_replicas = {}  # Store initial replicas for each service
        self.running_threads = {}  # Store active monitoring threads for each service
        self.stop_events = {}  # Store stop event flags for each service
        self.scaling_configs = {}  # Store scaling configurations for each service
        self.last_scale_down_time = {}  # Store last scale down time for each service

    def set_scaling_config(self, service_id, scaling_config):
        """Set the scaling configuration for a given service ID."""
        self.scaling_configs[service_id] = scaling_config

    def get_scaling_config(self, service_id):
        """Retrieve the scaling configuration for a given service ID."""
        return self.scaling_configs.get(service_id, None)

    def monitor_single_service(self, service_id, cluster_id):
        """
        Monitor a single service in a background thread.
        """
        print("Thread monitoring service ", service_id)
        try:
            scaling_config = self.get_scaling_config(service_id)
            if not scaling_config:
                print(f"No scaling config found for service {service_id}")
                return

            metrics = self.get_service_metrics(service_id)
            if not metrics:
                print(f"Failed to get metrics for service {service_id}, skipping monitoring cycle.")
                return

            cpu_usage_per_container = metrics["cpu_per_container"]
            ram_usage_per_container = metrics["ram_per_container"]
            current_replicas = metrics["replica_count"]

            # Track initial replica count
            if service_id not in self.initial_replicas:
                self.initial_replicas[service_id] = current_replicas

            initial_replicas = self.initial_replicas[service_id]

            avg_cpu = sum(cpu_usage_per_container) / len(cpu_usage_per_container)
            avg_ram = sum(ram_usage_per_container) / len(ram_usage_per_container)

            overloaded = avg_cpu > scaling_config["cpu_threshold"] or avg_ram > scaling_config["ram_threshold"]

            # Scale Up Logic
            if overloaded and current_replicas < scaling_config["max_replicas"]:
                new_replica_count = min(scaling_config["max_replicas"], current_replicas + 1)

                if is_cluster_full(cluster_id):
                    # If cluster is full, scale normally across all clusters
                    self.scale_service_to_count(service_id, new_replica_count, initial_replicas)
                else:
                    # If cluster has capacity, scale in the same cluster
                    self.scale_up_service_by_cluster(service_id, cluster_id)

            # Scale Down Logic
            elif not overloaded and current_replicas > scaling_config["min_replicas"]:
                last_time = self.last_scale_down_time.get(service_id, 0)

                if (time.time() - last_time) > scaling_config.get("cooldown_seconds", 30):
                    self.last_scale_down_time[service_id] = time.time()
                    new_replica_count = max(scaling_config["min_replicas"], current_replicas - 1)
                    self.scale_service_to_count(service_id, new_replica_count, current_replicas)

        except Exception as e:
            print(f"Error monitoring service {service_id}: {e}")

    def start_monitoring_services(self, service_id, scaling_config, check_interval, cluster_id):
        """
        Start monitoring a service in a background thread.
        If the service is already being monitored, it will not start a duplicate thread.
        """
        if service_id in self.running_threads:
            print(f"Service {service_id} is already being monitored.")
            return

        self.set_scaling_config(service_id, scaling_config)

        stop_event = Event()
        self.stop_events[service_id] = stop_event

        def monitor_loop():
            while not stop_event.is_set():
                self.monitor_single_service(service_id, cluster_id)
                time.sleep(int(check_interval))

        monitor_thread = Thread(target=monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()
        self.running_threads[service_id] = monitor_thread
        print(f"Started monitoring service {service_id}")

    def stop_monitoring_service(self, service_id):
        """
        Stop monitoring a specific service by setting the stop event.
        """
        if service_id in self.stop_events:
            self.stop_events[service_id].set()
            self.running_threads.pop(service_id, None)
            self.stop_events.pop(service_id, None)
            self.scaling_configs.pop(service_id, None)
            print(f"Stopped monitoring service {service_id}")
        else:
            print(f"Service {service_id} is not being monitored.")
