import os
import json
import requests
from pymongo import MongoClient


MONGO_ROOT_URI = os.environ.get("MONGO_ROOT_URI", "mongodb://46.249.99.42:10007/")
DATABASE_ROOT_NAME = os.environ.get("DATABASE_ROOT_NAME", "clusters")
COLLECTION_ROOT_NAME = os.environ.get("COLLECTION_ROOT_NAME", "clusters")

SYSTEM_MANAGER_ADDR = (
    "http://"
    + os.environ.get("SYSTEM_MANAGER_URL", "46.249.99.42")
    + ":"
    + str(os.environ.get("SYSTEM_MANAGER_PORT", "10000"))
)

CLUSTER_MANAGER_ADDR = (
    "http://"
    + os.environ.get("CLUSTER_MANAGER_URL", "46.249.99.42")
    + ":"
    + str(os.environ.get("CLUSTER_MANAGER_PORT", "10105"))
)

token = None


def login_to_system_manager():
    """
    Login to the System Manager.
    """
    request_address = SYSTEM_MANAGER_ADDR + "/api/auth/login"
    try:
        response = requests.post(request_address, json={"username": "Admin", "password": "Admin"})
        if response.status_code == 200:
            global token
            token = response.json()["token"]
            print("Successfully logged in to System Manager")
        else:
            print(f"Failed to login to System Manager. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error logging in to System Manager: {e}")


def deploy_request(cluster_id, job_id):
    """
    Deploy a job to a cluster.
    """
    request_address = SYSTEM_MANAGER_ADDR + "/api/result/deploy"
    try:
        requests.post(
            request_address,
            json={"cluster_id": cluster_id, "job_id": job_id},
            headers={"Authorization": f"Bearer {token}"}
        )
    except requests.exceptions.RequestException:
        print("Calling System Manager /api/result/deploy not successful.")


def get_service_cluster_id(service_id):
    """
    Get cluster id of a service, it will fetch all the instances and set a cluster that has most replicas in it.
    """
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}"
    try:
        response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            service_data = response.json()
            instance_list = []
            if isinstance(service_data, str):
                service_data = json.loads(service_data)
            if isinstance(service_data, dict) and "instance_list" in service_data:
                instance_list = service_data["instance_list"]

            cluster_counts = {}
            for instance in instance_list:
                cluster_id = instance.get("cluster_id")
                if cluster_id:
                    cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

            if cluster_counts:
                most_common_cluster = max(cluster_counts.items(), key=lambda x: x[1])[0]
                return most_common_cluster

            return None
        else:
            print(f"Failed to get service data. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting service data: {e}")
        return None


def get_cluster_ip_by_id(cluster_id):
    """
    Get cluster ip by id.
    """
    request_address = SYSTEM_MANAGER_ADDR + "/api/clusters"
    try:
        response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            cluster_data = response.json()
            for cluster in cluster_data:
                if cluster["_id"] == cluster_id:
                    return cluster["ip"]
            return None
        else:
            print(f"Failed to get cluster data. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting cluster data: {e}")
        return None


def get_hca_data(cluster_ip, service_id):
    """
    Get hca data from cluster hca.
    """
    request_address = f"http://{cluster_ip}:10180/api/v1/hca/{service_id}"
    try:
        response = requests.get(request_address)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get HCA data. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting HCA data: {e}")
        return None


def post_hca_monitor_data(cluster_ip, service_id, data):
    """
    Post hca data to cluster hca.
    """
    request_address = f"http://{cluster_ip}:10180/api/v1/hca/{service_id}"
    try:
        response = requests.post(request_address, json=data)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to post HCA monitor data. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error posting HCA monitor data: {e}")
        return None


def delete_hca_monitor_data(cluster_ip, service_id):
    """
    Delete hca data from cluster hca.
    """
    request_address = f"http://{cluster_ip}:10180/api/v1/hca/{service_id}"
    try:
        response = requests.delete(request_address)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error deleting HCA monitor data: {e}")


def put_hca_monitor_data(cluster_ip, service_id, data):
    """
    Put hca data to cluster hca.
    """
    request_address = f"http://{cluster_ip}:10180/api/v1/hca/{service_id}"
    try:
        response = requests.put(request_address, json=data)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error putting HCA monitor data: {e}")


def post_manual_scale(cluster_ip, data):
    """
    Post manual scale data to cluster hca.
    """
    request_address = f"http://{cluster_ip}:10180/api/v1/hca/manual"
    try:
        response = requests.post(request_address, json=data)
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Error posting manual scale: {e}")