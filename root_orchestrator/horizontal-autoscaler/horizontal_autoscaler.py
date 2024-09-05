import os

from flask import Flask
from hca_logging import configure_logging

MY_PORT = os.environ.get("MY_PORT")
CHECK_INTERVAL = os.environ.get("CHECK_INTERVAL")

my_logger = configure_logging()

app = Flask(__name__)

# SCALING_CONFIG = {
#     "cpu_threshold": 75,  # CPU usage percentage to trigger scaling
#     "memory_threshold": 80,  # Memory usage percentage to trigger scaling
#     "scale_up_max": 10,
#     "scale_down_min": 1,
# }


@app.route("/")
def hello_world():
    return "Hello, World! This is the horizontal_autoscaler.\n"


@app.route("/status")
def status():
    return "ok"


# @app.route("/manual_scale/<service_id>", methods=["POST"])
# def manual_scale(service_id):
#     try:
#         scale_data = request.get_json()
#         scale_type = scale_data.get("scale_type")  # Either "up" or "down"
#         if scale_type == "up":
#             scale_service_up(service_id, SCALING_CONFIG["scale_up_margin"])
#         elif scale_type == "down":
#             scale_service_down(service_id, SCALING_CONFIG["scale_down_margin"])
#         return jsonify({"message": f"Scaling {scale_type} triggered for service {service_id}"})
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(MY_PORT))
