import time
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

myPath = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, myPath + "/../")

from monitor_container_state import ServiceScaler

class TestServiceScaler(unittest.TestCase):
    def setUp(self):
        self.service_scaler = ServiceScaler()
        self.service_id = "service1"
        self.cluster_id = "cluster1"

        # Scaling Configurations
        self.service_scaler.get_scaling_config = MagicMock(return_value={
            "cpu_threshold": 80,
            "ram_threshold": 70,
            "max_replicas": 5,
            "min_replicas": 1,
            "cooldown_seconds": 0
        })

        # Mocking Methods
        self.service_scaler.get_service_metrics = MagicMock()
        self.service_scaler.scale_service_to_count = MagicMock()
        self.service_scaler.scale_up_service_by_cluster = MagicMock()

        # Mocking time
        self.service_scaler.last_scale_down_time = {}

    @patch("monitor_container_state.is_cluster_full", return_value=True)
    def test_scale_up_due_to_high_cpu(self, mock_is_cluster_full):
        """ Test scaling up when CPU usage is too high """
        self.service_scaler.get_service_metrics.return_value = {
            "cpu_per_container": [90, 85, 80],  # High CPU usage
            "ram_per_container": [50, 40, 30],  # RAM is fine
            "replica_count": 3,
        }

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        self.service_scaler.scale_service_to_count.assert_called_once_with(self.service_id, 4, 1)
 
    @patch("monitor_container_state.is_cluster_full", return_value=False)
    def test_scale_up_with_cluster_capacity(self, mock_is_cluster_full):
        """ Test scaling up within the same cluster when CPU is high """
        self.service_scaler.get_service_metrics.return_value = {
            "cpu_per_container": [95, 90, 85],  # High CPU
            "ram_per_container": [50, 45, 40],  # RAM is fine
            "replica_count": 2,
        }

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        # Should trigger scale within the cluster
        self.service_scaler.scale_up_service_by_cluster.assert_called_once_with(self.service_id, self.cluster_id)

    def test_no_scaling_when_usage_is_normal(self):
        """ Ensure no scaling happens when CPU & RAM are below thresholds """
        self.service_scaler.get_service_metrics.return_value = {
            "cpu_per_container": [50, 45, 40],  # Low CPU
            "ram_per_container": [50, 45, 40],  # Low RAM
            "replica_count": 3,
        }

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        self.service_scaler.scale_service_to_count.assert_called_once_with(self.service_id, 2, 3)
        self.service_scaler.scale_up_service_by_cluster.assert_not_called()

    def test_scaling_down_when_below_threshold(self):
        """ Test scaling down when CPU & RAM usage are low """
        self.service_scaler.get_service_metrics.return_value = {
            "cpu_per_container": [30, 25, 20],  # Low CPU
            "ram_per_container": [30, 25, 20],  # Low RAM
            "replica_count": 3,
        }

        # Mock cooldown time to allow scaling down
        self.service_scaler.last_scale_down_time[self.service_id] = time.time() - 100

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        # Should trigger scale down
        self.service_scaler.scale_service_to_count.assert_called_once_with(self.service_id, 2, 3)

    def test_does_not_scale_below_min_replicas(self):
        """ Ensure scaling down does not go below min_replicas """
        self.service_scaler.get_service_metrics.return_value = {
            "cpu_per_container": [30, 25, 20],  # Low CPU
            "ram_per_container": [30, 25, 20],  # Low RAM
            "replica_count": 1,  # Already at min_replicas
        }

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        # No scale down should occur
        self.service_scaler.scale_service_to_count.assert_not_called()

    def test_no_action_if_no_scaling_config(self):
        """ Test when scaling config is missing """
        self.service_scaler.get_scaling_config.return_value = None

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        # No action should be taken
        self.service_scaler.scale_service_to_count.assert_not_called()

    def test_no_action_if_no_metrics(self):
        """ Test when metrics cannot be fetched """
        self.service_scaler.get_service_metrics.return_value = None

        self.service_scaler.monitor_single_service(self.service_id, self.cluster_id)

        # No action should be taken
        self.service_scaler.scale_service_to_count.assert_not_called()

if __name__ == "__main__":
    unittest.main()

