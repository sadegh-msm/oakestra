from pymongo import MongoClient
from threading import Lock
import os


MONGO_CLUSTER_URI = os.environ.get("MONGO_CLUSTER_URI", "mongodb://46.249.99.42:10107/")
DATABASE_CLUSTER_HCA = os.environ.get("DATABASE_CLUSTER_HCA", "horizontal_autoscaler")
COLLECTION_CLUSTER_HCA = os.environ.get("COLLECTION_CLUSTER_HCA", "scaling_data")

client = MongoClient(MONGO_CLUSTER_URI)
db = client[DATABASE_CLUSTER_HCA]
scaling_data = db[COLLECTION_CLUSTER_HCA]


mongo_lock = Lock()


def set_scaling_config(service_id, scaling_config):
    """
    Set the scaling config for a service.
    """
    try:
        with mongo_lock:
            scaling_data.update_one({"service_id": service_id}, {"$set": scaling_config}, upsert=True)
    except Exception as e:
        print(e)


def get_scaling_config(service_id):
    """
    Get the scaling config for a service.
    """
    try:
        with mongo_lock:
            result = scaling_data.find_one({"service_id": service_id})
        return result
    except Exception as e:
        print(e)
        return None


def restore_scaling_configs(scaler):
    """
    Restore the scaling configs from the database.
    """
    try:
        with mongo_lock:
            configs = list(scaling_data.find())

        for config in configs:
            service_id = config["service_id"]
            cluster_id = config["cluster_id"]
            check_interval = config.get("check_interval", 30)
            print(f"Restoring monitoring for service {service_id}")
            scaler.start_monitoring_services(service_id, config, check_interval, cluster_id)
    except Exception as e:
        print(e)


def delete_scaling_config(service_id):
    """
    Delete the scaling config for a service.
    """
    try:
        with mongo_lock:
            scaling_data.delete_one({"service_id": service_id})
    except Exception as e:
        print(e)
