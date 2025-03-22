import os

import requests
from pymongo import MongoClient

MONGO_URI = "mongodb://46.249.99.42:10107/"
DATABASE_NAME = "jobs"
COLLECTION_NAME = "jobs"

SYSTEM_MANAGER_ADDR = (
    "http://"
    + os.environ.get("SYSTEM_MANAGER_URL", "46.249.99.42")
    + ":"
    + str(os.environ.get("SYSTEM_MANAGER_PORT", "10000"))
)

CLUSTER_MANAGER_ADDR = (
    "http://"
    + os.environ.get("CLUSTER_MANAGER_URL", "127.0.0.1")
    + ":"
    + str(os.environ.get("CLUSTER_MANAGER_PORT", "10105"))
)

ROOT_HCA_ADDR = (
    "http://"
    + os.environ.get("ROOT_HCA_URL", "46.249.99.42")
    + ":"
    + str(os.environ.get("ROOT_HCA_PORT", "10080"))
)

token = None

def login_to_system_manager():
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

# def manager_deploy_request(cluster_id, job_id):
#     request_address = SYSTEM_MANAGER_ADDR + "/api/result/deploy"
#     try:
#         requests.post(
#             request_address,
#             json={"cluster_id": cluster_id, "job_id": job_id},
#             headers={"Authorization": f"Bearer {token}"}
#         )
#     except requests.exceptions.RequestException:
#         print("Calling System Manager /api/result/deploy not successful.")

# def cluster_deploy_request(job_id, instance_num):
#     request_address = SYSTEM_MANAGER_ADDR + f"/api/calculate/deploy/{job_id}/{instance_num}"
#     try:
#         response = requests.post(request_address, headers={"Authorization": f"Bearer {token}"})
#         if response.status_code == 200:
#             print(f"Successfully sent deploy request for job {job_id}, instance {instance_num}")
#         else:
#             print(f"Failed to send deploy request. Status code: {response.status_code}")
#     except requests.exceptions.RequestException as e:
#         print(f"Error sending deploy request: {e}")

def cluster_deploy_request(job_id, instance_num):
    request_address = CLUSTER_MANAGER_ADDR + f"/api/calculate/deploy/{job_id}/{instance_num}"
    try:
        response = requests.post(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print(f"Successfully sent deploy request for job {job_id}, instance {instance_num}")
        else:
            print(f"Failed to send deploy request. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending deploy request: {e}")

def delete_instance_from_service(service_id, instance_id):
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}/instance/{instance_id}"
    try:
        requests.delete(request_address, headers={"Authorization": f"Bearer {token}"})
    except requests.exceptions.RequestException:
        print("Calling System Manager /api/service/{service_id}/instance/{instance_id} not successful.")

def create_instance_for_service(service_id):
    print("Creating new instance for service...")
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}/instance"
    try:
        response = requests.post(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print(f"Successfully created new instance for service {service_id}")
        else:
            print(f"Failed to create instance for service {service_id}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error creating instance for service {service_id}: {e}")

def get_service_data(service_id):
    """Fetch service data from MongoDB and extract CPU and RAM usage for all instances."""
    try:
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        service_data = collection.find_one({"system_job_id": service_id})

        if not service_data:
            print(f"No data found for service_id: {service_id}")

        instance_list = service_data.get("instance_list", [])
        cpu_usage = [float(instance.get("cpu", 0)) for instance in instance_list]
        ram_usage = [float(instance.get("memory", 0)) for instance in instance_list]

        return {
            "cpu_per_container": cpu_usage,
            "ram_per_container": ram_usage,
            "replica_count": len(instance_list),
        }

    except Exception as e:
        print(f"Error fetching service data: {e}")

def get_instance_list(service_id):
    """Get list of instances for a service from the System Manager API."""
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}"
    try:
        response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            service_data = response.json()
            instance_list = service_data.get("instance_list", [])
            return instance_list
        else:
            print(f"Failed to get instances for service {service_id}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error getting instances for service {service_id}: {e}")

# def get_all_clusters():
#     """Get a mapping of cluster names to cluster IDs."""
#     try:
#         request_address = SYSTEM_MANAGER_ADDR + "/api/clusters"
#         response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        
#         if response.status_code == 200:
#             clusters = response.json()
#             cluster_map = {cluster["cluster_name"]: str(cluster["_id"]) for cluster in clusters}
#             return cluster_map
#         else:
#             print(f"Failed to get clusters. Status code: {response.status_code}")

#     except requests.exceptions.RequestException as e:
#         print(f"Error getting clusters: {e}")

def get_all_jobs():
    request_address = CLUSTER_MANAGER_ADDR + "/api/services"
    try:
        response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            services = response.json()
            service_map = {str(service["_id"]): service["job_name"] for service in services}
            return service_map
        else:
            print(f"Failed to get services. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error getting services: {e}")


def root_hca_scale_request(service_id):
    request_address = ROOT_HCA_ADDR + f"/api/hca/{service_id}"
    try:
        response = requests.post(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print(f"Successfully sent deploy request for job {service_id}")
        else:
            print(f"Failed to send deploy request. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending deploy request: {e}")

def get_next_instance_num(service_id):
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}"
    try:
        response = requests.get(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            service_data = response.json()
            return service_data.get("next_instance_progressive_number")
        else:
            print(f"Failed to get next instance number for service {service_id}. Status code: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error getting next instance number for service {service_id}: {e}")
        return None
