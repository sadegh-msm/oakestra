import os
import json
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId

MONGO_CLUSTER_URI = os.environ.get("MONGO_CLUSTER_URI", "mongodb://46.249.99.42:10107/")
DATABASE_CLUSTER_NAME = os.environ.get("DATABASE_CLUSTER_NAME", "jobs")
COLLECTION_CLUSTER_NAME = os.environ.get("COLLECTION_CLUSTER_NAME", "jobs")

MONGO_ROOT_URI = os.environ.get("MONGO_ROOT_URI", "mongodb://46.249.99.42:10007/")
DATABASE_ROOT_NAME = os.environ.get("DATABASE_ROOT_NAME", "clusters")
COLLECTION_ROOT_NAME = os.environ.get("COLLECTION_ROOT_NAME", "clusters")

SYSTEM_MANAGER_ADDR = (
    "http://"
    + os.environ.get("SYSTEM_MANAGER_URL", "46.249.99.42")
    + ":"
    + str(os.environ.get("SYSTEM_MANAGER_PORT", "10000"))
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


def manager_deploy_request(cluster_id, job_id):
    """
    Deploy a job to a cluster.
    """
    request_address = SYSTEM_MANAGER_ADDR + "/api/result/deploy"
    try:
        response = requests.post(
            request_address,
            json={"cluster_id": cluster_id, "job_id": job_id},
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code == 200:
            print(f"Successfully deployed job {job_id} to cluster {cluster_id}")
        elif response.status_code == 401:
            login_to_system_manager()
            manager_deploy_request(cluster_id, job_id)
        else:
            print(f"Failed to deploy job {job_id} to cluster {cluster_id}. Status code: {response.status_code}")

    except requests.exceptions.RequestException:
        print("Calling System Manager /api/result/deploy not successful.")


def delete_instance_from_service(service_id, instance_id):
    """
    Delete an instance from a service.
    """
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}/instance/{instance_id}"
    try:
        response = requests.delete(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print(f"Successfully deleted instance {instance_id} from service {service_id}")
        elif response.status_code == 401:
            login_to_system_manager()
            delete_instance_from_service(service_id, instance_id)
        else:
            print(f"Failed to delete instance {instance_id} from service {service_id}. Status code: {response.status_code}")

    except requests.exceptions.RequestException:
        print("Calling System Manager /api/service/{service_id}/instance/{instance_id} not successful.")


def create_instance_for_service(service_id):
    """
    Create a new instance for a service.
    """
    print("Creating new instance for service...")
    request_address = SYSTEM_MANAGER_ADDR + f"/api/service/{service_id}/instance"
    try:
        response = requests.post(request_address, headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 200:
            print(f"Successfully created new instance for service {service_id}")
        elif response.status_code == 401:
            login_to_system_manager()
            create_instance_for_service(service_id)
        else:
            print(f"Failed to create instance for service {service_id}. Status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error creating instance for service {service_id}: {e}")


def get_service_data(service_id):
    """Fetch service data from MongoDB and extract CPU and RAM usage for all instances."""
    try:
        client = MongoClient(MONGO_CLUSTER_URI)
        db = client[DATABASE_CLUSTER_NAME]
        collection = db[COLLECTION_CLUSTER_NAME]

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
            if isinstance(service_data, str):
                service_data = json.loads(service_data)

            instance_list = service_data.get("instance_list", [])

            return [instance["instance_number"] for instance in instance_list]
        elif response.status_code == 401:
            login_to_system_manager()
            get_instance_list(service_id)
        else:
            print(f"Failed to get instances for service {service_id}. Status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"Error getting instances for service {service_id}: {e}")


def is_cluster_full(cluster_id):
    """
    Check if a cluster is full.
    """
    client = MongoClient(MONGO_ROOT_URI)
    db = client[DATABASE_ROOT_NAME]
    collection = db[COLLECTION_ROOT_NAME]

    cluster_data = collection.find_one({"_id": ObjectId(cluster_id)})
    if not cluster_data:
        return False

    cpu_history = cluster_data.get("cpu_history", [])
    memory_history = cluster_data.get("memory_history", [])
    total_cpu_cores = cluster_data.get("total_cpu_cores", 0)

    if not cpu_history or not memory_history:
        return False

    last_cpu = cpu_history[-1]["value"]
    last_memory = memory_history[-1]["value"]

    # return last_cpu >= (total_cpu_cores - (total_cpu_cores * 0.20)) or last_memory >= 80
    return last_cpu >= (total_cpu_cores - (total_cpu_cores * 0.80)) or last_memory >= 80

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
        elif response.status_code == 401:
            login_to_system_manager()
            get_service_cluster_id(service_id)
        else:
            print(f"Failed to get service data. Status code: {response.status_code}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error getting service data: {e}")
        return None