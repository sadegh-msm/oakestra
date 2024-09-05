import time
from threading import Thread


class ServiceScaler:
    def __init__(self, get_service_metrics, scale_service_to_count):
        self.get_service_metrics = get_service_metrics
        self.scale_service_to_count = scale_service_to_count
        self.initial_replicas = {}  # Dictionary to store initial replicas for each service

    def monitor_single_service(self, service_id, scaling_config):
        try:
            metrics = self.get_service_metrics(service_id)
            cpu_usage_per_container = metrics["cpu_per_container"]
            ram_usage_per_container = metrics["ram_per_container"]
            current_replicas = metrics["replica_count"]

            # Track initial replica count for the service
            if service_id not in self.initial_replicas:
                self.initial_replicas[service_id] = current_replicas

            initial_replicas = self.initial_replicas[service_id]

            overloaded_containers = sum(
                1
                for cpu, ram in zip(cpu_usage_per_container, ram_usage_per_container)
                if cpu > scaling_config["cpu_threshold"] or ram > scaling_config["ram_threshold"]
            )

            # Scale Up Logic
            if overloaded_containers > 0 and current_replicas < scaling_config["max_replicas"]:
                new_replica_count = min(
                    scaling_config["max_replicas"], current_replicas + overloaded_containers
                )
                self.scale_service_to_count(service_id, new_replica_count)

            # Scale Down Logic
            elif overloaded_containers == 0 and current_replicas > initial_replicas:
                new_replica_count = max(initial_replicas, current_replicas - 1)
                self.scale_service_to_count(service_id, new_replica_count)

        except Exception as e:
            print(f"Error monitoring service {service_id}: {e}")

    def start_monitoring_services(self, services, check_interval):
        for service in services:
            service_id = service["id"]
            scaling_config = service["scaling_config"]  # Get the scaling config for each service
            monitor_thread = Thread(
                target=self.monitor_single_service, args=(service_id, scaling_config)
            )
            monitor_thread.daemon = True
            monitor_thread.start()

            # Sleep for the defined check interval
            time.sleep(check_interval)
