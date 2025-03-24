from pymongo import MongoClient
from other_requests import get_service_cluster_id
import os


MONGO_ROOT_URI = os.environ.get("MONGO_ROOT_URI", "mongodb://46.249.99.42:10007/")
DATABASE_ROOT_HCA = os.environ.get("DATABASE_ROOT_HCA", "horizontal_autoscaler")
COLLECTION_ROOT_HCA = os.environ.get("COLLECTION_ROOT_HCA", "service_cluster_mapping")

client = MongoClient(MONGO_ROOT_URI)
db = client[DATABASE_ROOT_HCA]
service_cluster_mapping = db[COLLECTION_ROOT_HCA]


def get_service_cluster(service_id):
    """
    Get cluster ID for a service from MongoDB mapping or find it if not exists
    """
    mapping = service_cluster_mapping.find_one({'service_id': service_id})

    if mapping:
        return mapping['cluster_id']

    cluster_id = find_cluster(service_id)
    if cluster_id is None:
        print(f"Error finding cluster for service {service_id}")
        return None

    if cluster_id:
        service_cluster_mapping.insert_one({
            'service_id': service_id,
            'cluster_id': cluster_id
        })
        return cluster_id

    return None


def find_cluster(service_id):
    """
    Find cluster ID for a service by calling system manager API
    """
    try:
        response = get_service_cluster_id(service_id)
        if response:
            return response
        else:
            return None
    except Exception as e:
        print(f"Error finding cluster for service {service_id}: {e}")
    return None