from pymongo import MongoClient
from other_requests import get_service_cluster_id


client = MongoClient('mongodb://46.249.99.42:10007/')
db = client['horizontal_autoscaler']
service_cluster_mapping = db['service_cluster_mapping']


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