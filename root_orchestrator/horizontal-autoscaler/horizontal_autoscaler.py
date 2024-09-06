import os

from flask import Flask, jsonify
from flask.views import MethodView
from flask_swagger_ui import get_swaggerui_blueprint
from flask_smorest import Blueprint
from marshmallow import INCLUDE, Schema, fields
from hca_logging import configure_logging
from helper import (
    service_autoscaler,
    get_service_autoscaler_data,
    manual_scale,
)

MY_PORT = os.environ.get("MY_PORT")
CHECK_INTERVAL = os.environ.get("CHECK_INTERVAL")

my_logger = configure_logging()

app = Flask(__name__)

app.config["OPENAPI_VERSION"] = "3.0.2"
app.config["API_TITLE"] = "Resource Abstractor Api"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_URL_PREFIX"] = "/docs"

SWAGGER_URL = "/api/docs"
API_URL = "/docs/openapi.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Resource Abstractor"},
)

scalerblp = Blueprint(
    "horizontal autoscaler Operations",
    "applications",
    url_prefix="/api/v1/hca",
    description="Operations on applications",
)

app.register_blueprint(scalerblp)
app.register_blueprint(swaggerui_blueprint)


class AutoscalerFilterSchema(Schema):
    cpu_threshold = fields.Int()
    ram_threshold = fields.Int()
    min_replicas = fields.Int()
    max_replicas = fields.Int()


class ManualScaleFilterSchema(Schema):
    job_id = fields.String()
    cluster_id = fields.String()
    scale_type = fields.String()  # up and down


@app.route("/")
def hello_world():
    return "Hello, World! This is the horizontal_autoscaler.\n"


@app.route("/status")
def status():
    return "ok"


@scalerblp.route("/<service_id>")
class HorizontalAutoscalerController(MethodView):
    def get(self, service_id):
        try:
            result = get_service_autoscaler_data(service_id)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @scalerblp.arguments(AutoscalerFilterSchema(unknown=INCLUDE), location="json")
    def post(self, data, **kwargs):
        service_id = kwargs.get("service_id")

        try:
            if not all(
                k in data
                for k in ["cpu_threshold", "ram_threshold", "max_replicas", "min_replicas"]
            ):
                return jsonify({"error": "Missing required autoscaler parameters"}), 400

            service_autoscaler(data, service_id, CHECK_INTERVAL)
            return jsonify({"message": f"Adding autoscaler for service {service_id}"}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@scalerblp.route("/manual")
class HorizontalScaleManualyByCluster(MethodView):
    @scalerblp.arguments(ManualScaleFilterSchema(unknown=INCLUDE), location="json")
    def post(self, data, **kwargs):
        try:
            return manual_scale(data)

        except Exception as e:
            return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="::", port=int(MY_PORT), debug=False)
