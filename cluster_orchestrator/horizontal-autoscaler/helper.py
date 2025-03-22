from monitor_container_state import ServiceScaler
from flask import jsonify
from other_requests import *


def get_service_metrics(service_id):
    return get_service_data(service_id)


def scale_service_to_count(service_id, new_replica_count, initial_replicas):
    if new_replica_count > initial_replicas:
        for i in range(initial_replicas, new_replica_count):
            create_instance_for_service(service_id)
    else:
        for i in range(initial_replicas, new_replica_count, -1):
            delete_instance_from_service(service_id, i)

def service_autoscaler(autoscaler_data, service_id, check_interval):
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count)
    scaler.start_monitoring_services(service_id, autoscaler_data, check_interval)

def delete_service_autoscaler(service_id):
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count)
    scaler.stop_monitoring_service(service_id)

def get_service_autoscaler_data(service_id):
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count)
    return scaler.get_scaling_config(service_id)


def scale_service_up(service_id):
    service_data = get_service_data(service_id)
    if service_data is None:
        return jsonify({"message": f"Service {service_id} not found"})
    initial_replicas = service_data["replica_count"]
    new_replica_count = initial_replicas + 1
    scale_service_to_count(service_id, new_replica_count, initial_replicas)


def scale_service_down(service_id):
    service_data = get_service_data(service_id)
    if service_data is None:
        return jsonify({"message": f"Service {service_id} not found"})
    initial_replicas = service_data["replica_count"]
    new_replica_count = initial_replicas - 1
    scale_service_to_count(service_id, new_replica_count, initial_replicas)


def scale_up_service_by_cluster(service_id, instance_num):
    cluster_deploy_request(service_id, instance_num)


def manual_scale(data):
    scale_type = data["scale_type"]  # Either "up" or "down"
    service_id = data["job_id"]
    cluster_name = data["cluster_name"]
    if cluster_name == "":
        if scale_type == "up":
            scale_service_up(service_id)
        elif scale_type == "down":
            scale_service_down(service_id)
        return jsonify({"message": f"Scaling {scale_type} triggered for service {service_id}"})

    else:
        if scale_type == "up":
            instance_num = get_next_instance_num(service_id)
            scale_up_service_by_cluster(service_id, instance_num)
        elif scale_type == "down":
            scale_service_down(service_id)
        return jsonify(
            {"message": f"Scaling by cluster_id {scale_type} triggered for service {service_id}"}
        )
