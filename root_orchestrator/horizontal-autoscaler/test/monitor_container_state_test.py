import os
import sys
import unittest
from unittest.mock import Mock

# from monitor_container_state import ServiceScaler

myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + "/../")

from monitor_container_state import ServiceScaler


class TestServiceScaler(unittest.TestCase):
    def setUp(self):
        self.get_service_metrics = Mock()
        self.scale_service_to_count = Mock()
        self.service_scaler = ServiceScaler(self.get_service_metrics, self.scale_service_to_count)

        # Define sample scaling configurations for the test
        self.scaling_config = {
            "cpu_threshold": 80,
            "ram_threshold": 70,
            "max_replicas": 5,
            "min_replicas": 1,
            "check_interval": 1,  # Short interval for faster testing
        }

    def test_no_scaling_needed(self):
        # Simulate metrics where no scaling is needed (3 replicas, no overload)
        self.get_service_metrics.return_value = {
            "cpu_per_container": [50, 30, 40],  # All below CPU threshold
            "ram_per_container": [60, 30, 40],  # All below RAM threshold
            "replica_count": 3,  # Current replica count
        }
        service_id = "service1"
        self.service_scaler.monitor_single_service(service_id, self.scaling_config)

        # Ensure scale_service_to_count is not called
        self.scale_service_to_count.assert_not_called()

    def test_cpu_usage_over_100_percent(self):
        # Simulate metrics where one container's CPU usage is over 100% (with 3 replicas)
        self.get_service_metrics.return_value = {
            "cpu_per_container": [110, 60, 50],  # One container with 110% CPU usage
            "ram_per_container": [50, 40, 30],  # RAM usage is below the threshold
            "replica_count": 3,  # Current replica count
        }
        service_id = "service1"
        self.service_scaler.monitor_single_service(service_id, self.scaling_config)

        # Expect scaling up by 1 replica (since one container is overloaded)
        self.scale_service_to_count.assert_called_once_with(service_id, 4)

    def test_cpu_usage_over_500_percent(self):
        # Simulate metrics where one container's CPU usage is over 500% (with 3 replicas)
        self.get_service_metrics.return_value = {
            "cpu_per_container": [500, 600, 40],  # One container with 500% CPU usage
            "ram_per_container": [50, 40, 30],  # RAM usage is below the threshold
            "replica_count": 3,  # Current replica count
        }
        service_id = "service1"
        self.service_scaler.monitor_single_service(service_id, self.scaling_config)

        # Expect scaling up by 1 replica (since one container is severely overloaded)
        self.scale_service_to_count.assert_called_once_with(service_id, 5)

    def test_scaling_down_but_not_below_initial_replicas(self):
        # Simulate metrics where no containers are overloaded, but there are more than min_replicas
        self.get_service_metrics.return_value = {
            "cpu_per_container": [50, 30, 40],  # All below CPU threshold
            "ram_per_container": [60, 30, 40],  # All below RAM threshold
            "replica_count": 3,  # Current replica count (above min_replicas)
        }
        service_id = "service1"
        self.service_scaler.monitor_single_service(service_id, self.scaling_config)

        # Ensure that scaling down by 1 replica is called
        self.scale_service_to_count.assert_not_called()


if __name__ == "__main__":
    unittest.main()
