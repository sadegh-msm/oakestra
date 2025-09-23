from monitor_container_state import ServiceScaler
from flask import jsonify
from other_requests import (
    create_instance_for_service,
    get_service_data,
    get_instance_list,
    delete_instance_from_service,
    manager_deploy_request,
)
from horizontal_autoscaler_db import restore_scaling_configs, get_scaling_config


def get_service_metrics(service_id):
    return get_service_data(service_id)


def restore_scaling():
    """
    Restore the scaling configs from the database.
    """
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count, scale_up_service_by_cluster)
    restore_scaling_configs(scaler)


def scale_service_to_count(service_id, new_replica_count, current_replicas):
    """
    Scale a service to a new replica count.
    """
    if new_replica_count > current_replicas:
        # Scale UP
        for i in range(current_replicas, new_replica_count):
            create_instance_for_service(service_id)

    elif new_replica_count < current_replicas:
        # Scale DOWN
        for i in range(current_replicas, new_replica_count, -1):
            instance_list = get_instance_list(service_id)
            delete_instance_from_service(service_id, instance_list[-1])


def service_autoscaler(autoscaler_data, service_id, check_interval, cluster_id):
    """
    Start the service autoscaler.
    """
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count, scale_up_service_by_cluster)
    scaler.start_monitoring_services(service_id, autoscaler_data, check_interval, cluster_id)


def delete_service_autoscaler(service_id):
    """
    Delete the service autoscaler.
    """
    scaler = ServiceScaler(get_service_metrics, scale_service_to_count, scale_up_service_by_cluster)
    scaler.stop_monitoring_service(service_id)


def get_service_autoscaler_data(service_id):
    """
    Get the service autoscaler data.
    """
    return get_scaling_config(service_id)


def scale_service_up(service_id):
    """
    Scale a service up.
    """
    service_data = get_service_data(service_id)
    if service_data is None:
        return jsonify({"message": f"Service {service_id} not found"})
    create_instance_for_service(service_id)


def scale_service_down(service_id):
    """
    Scale a service down.
    """
    service_data = get_service_data(service_id)
    if service_data is None:
        return jsonify({"message": f"Service {service_id} not found"})

    instance_list = get_instance_list(service_id)
    if len(instance_list) == 1:
        return jsonify({"message": f"Service {service_id} has only one instance, cannot scale down"})
    else:
        delete_instance_from_service(service_id, instance_list[-1])
        return jsonify({"message": f"Service {service_id} scaled down"})


def scale_up_service_by_cluster(service_id, cluster_id):
    """
    Scale a service up by cluster.
    """
    manager_deploy_request(cluster_id, service_id)


def manual_scale(data):
    """
    Manually scale a service.
    """
    scale_type = data["scale_type"]  # Either "up" or "down"
    service_id = data["service_id"]
    cluster_id = data["cluster_id"]
    if cluster_id is None:
        if scale_type == "up":
            scale_service_up(service_id)
        elif scale_type == "down":
            return scale_service_down(service_id)
        return jsonify({"message": f"Scaling {scale_type} triggered for service {service_id}"})

    else:
        if scale_type == "up":
            scale_up_service_by_cluster(service_id, cluster_id)
        elif scale_type == "down":
            return scale_service_down(service_id)
        return jsonify(
            {"message": f"Scaling by cluster_id {scale_type} triggered for service {service_id}"}
        )
