from monitor_container_state import ServiceScaler
from flask import jsonify
from manager_requests import manager_deploy_request


def get_service_metrics(service_id):
    pass


def scale_service_to_count(service_id, new_replica_count, initial_replicas):
    pass


def service_autoscaler(autoscaler_data, service_id, check_interval):
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count)
    scaler.start_monitoring_services(service_id, autoscaler_data, check_interval)


def get_service_autoscaler_data(service_id):
    pass


def scale_service_up(service_id):
    pass


def scale_service_down(service_id):
    pass


def scale_service_down_by_cluster(service_id, cluster_id):
    pass


def manual_scale(data):
    scale_type = data["scale_type"]  # Either "up" or "down"
    service_id = data["job_id"]
    cluster_id = data["cluster_id"]
    if cluster_id == "":
        if scale_type == "up":
            scale_service_up(service_id)
        elif scale_type == "down":
            scale_service_down(service_id)
        return jsonify({"message": f"Scaling {scale_type} triggered for service {service_id}"})

    else:
        if scale_type == "up":
            manager_deploy_request(service_id, cluster_id)
        elif scale_type == "down":
            scale_service_down_by_cluster(service_id, cluster_id)
        return jsonify(
            {"message": f"Scaling by cluster_id {scale_type} triggered for service {service_id}"}
        )
