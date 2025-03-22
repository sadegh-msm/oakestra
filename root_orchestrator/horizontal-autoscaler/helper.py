from flask import jsonify
import requests
from pymongo import MongoClient
from other_requests import (
    get_service_cluster_id,
    get_cluster_ip_by_id,
    get_hca_data,
    post_hca_monitor_data,
    delete_hca_monitor_data,
    put_hca_monitor_data,
    post_manual_scale
)

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


def get_cluster_ip(cluster_id):
    """
    Get cluster IP for a cluster ID by calling system manager API
    """
    try:
        # response = get_cluster_ip_by_id(cluster_id)
        response = "127.0.0.1"
        if response:
            return response
        else:
            return None
    except Exception as e:
        print(f"Error getting cluster IP for cluster {cluster_id}: {e}")
    return None


def get_hca_data_from_cluster(service_id):
    """
    Get HCA data for a service by calling HCA API
    """
    try:
        cluster_id = get_service_cluster(service_id)
        if cluster_id:
            cluster_ip = get_cluster_ip(cluster_id)
            if cluster_ip:
                return get_hca_data(cluster_ip, service_id)
        else:
            print(f"Error getting cluster IP for service {service_id}")
            return jsonify({"error": f"Error getting cluster IP for service {service_id}"}), 500
    except Exception as e:
        print(f"Error getting HCA data for service {service_id}: {e}")
        return jsonify({"error": f"Error getting HCA data for service {service_id}: {e}"}), 500


def post_hca_monitor_data_to_cluster(service_id, data):
    """
    Post HCA data for a service by calling HCA API
    """
    try:
        cluster_id = get_service_cluster(service_id)
        if cluster_id:
            cluster_ip = get_cluster_ip(cluster_id)
            if cluster_ip:
                return post_hca_monitor_data(cluster_ip, service_id, data)
        else:
            print(f"Error getting cluster IP for service {service_id}")
            return jsonify({"error": f"Error getting cluster IP for service {service_id}"}), 500
    except Exception as e:
        print(f"Error posting HCA data for service {service_id}: {e}")
        return jsonify({"error": f"Error posting HCA data for service {service_id}: {e}"}), 500

def delete_hca_monitor_data_from_cluster(service_id):
    """
    Delete HCA data for a service by calling HCA API
    """
    try:
        cluster_id = get_service_cluster(service_id)
        if cluster_id:
            cluster_ip = get_cluster_ip(cluster_id)
            if cluster_ip:
                return delete_hca_monitor_data(cluster_ip, service_id)
        else:
            print(f"Error getting cluster IP for service {service_id}")
            return jsonify({"error": f"Error getting cluster IP for service {service_id}"}), 500
    except Exception as e:
        print(f"Error deleting HCA data for service {service_id}: {e}")
        return jsonify({"error": f"Error deleting HCA data for service {service_id}: {e}"}), 500


def put_hca_monitor_data_to_cluster(service_id, data):
    """
    Put HCA data for a service by calling HCA API
    """
    try:
        cluster_id = get_service_cluster(service_id)
        if cluster_id:
            cluster_ip = get_cluster_ip(cluster_id)
            if cluster_ip:
                return put_hca_monitor_data(cluster_ip, service_id, data)
        else:
            print(f"Error getting cluster IP for service {service_id}")
            return jsonify({"error": f"Error getting cluster IP for service {service_id}"}), 500
    except Exception as e:
        print(f"Error putting HCA data for service {service_id}: {e}")
        return jsonify({"error": f"Error putting HCA data for service {service_id}: {e}"}), 500


def post_manual_scale_to_cluster(service_id, data):
    """
    Post manual scale for a service by calling HCA API
    """
    try:
        cluster_id = get_service_cluster(service_id)
        if cluster_id:
            cluster_ip = get_cluster_ip(cluster_id)
            if cluster_ip:
                return post_manual_scale(cluster_ip, service_id, data)
        else:
            print(f"Error getting cluster IP for service {service_id}")
            return jsonify({"error": f"Error getting cluster IP for service {service_id}"}), 500
    except Exception as e:
        print(f"Error posting manual scale for service {service_id}: {e}")
        return jsonify({"error": f"Error posting manual scale for service {service_id}: {e}"}), 500