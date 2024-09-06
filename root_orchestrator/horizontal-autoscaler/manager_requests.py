import os

import requests

SYSTEM_MANAGER_ADDR = (
    "http://"
    + os.environ.get("SYSTEM_MANAGER_URL")
    + ":"
    + str(os.environ.get("SYSTEM_MANAGER_PORT"))
)


def manager_deploy_request(cluster, job_id):
    print("sending scheduling result to system-manager...")
    request_address = SYSTEM_MANAGER_ADDR + "/api/result/deploy"
    print(request_address)
    try:
        requests.post(
            request_address,
            json={"cluster_id": str(cluster.get("_id")), "job_id": job_id},
        )
    except requests.exceptions.RequestException:
        print("Calling System Manager /api/result/deploy not successful.")
