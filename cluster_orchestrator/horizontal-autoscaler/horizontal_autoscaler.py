import os

from flask import Flask, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint, Api
from flask_swagger_ui import get_swaggerui_blueprint
from marshmallow import INCLUDE, Schema, fields
from hca_logging import configure_logging
from helper import (
    service_autoscaler,
    get_service_autoscaler_data,
    manual_scale,
    delete_service_autoscaler,
    login_to_system_manager,
)

MY_PORT = os.environ.get("MY_PORT", "10180")
CHECK_INTERVAL = os.environ.get("CHECK_INTERVAL", "10")

my_logger = configure_logging()

app = Flask(__name__)

app.config["OPENAPI_VERSION"] = "3.0.2"
app.config["API_TITLE"] = "Horizontal Autoscaler Api"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_URL_PREFIX"] = "/docs"

api = Api(app, spec_kwargs={"title": app.config["API_TITLE"]})


SWAGGER_URL = "/api/docs"
API_URL = "/docs/openapi.json"
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Resource Abstractor"},
)

scalerblp = Blueprint(
    "horizontal autoscaler Operations",
    "hca",
    url_prefix="/api/v1/hca",
    description="Operations on hca",
)

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
    return "Hello, World! This is the cluster_horizontal_autoscaler.\n"


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

    def delete(self, service_id):
        try:
            delete_service_autoscaler(service_id)
            return jsonify({"message": f"Stopping autoscaler for service {service_id}"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @scalerblp.arguments(AutoscalerFilterSchema(unknown=INCLUDE), location="json")
    def update(self, data, service_id):
        try:
            if not all(
                k in data
                for k in ["cpu_threshold", "ram_threshold", "max_replicas", "min_replicas"]
            ):
                return jsonify({"error": "Missing required autoscaler parameters"}), 400

            delete_service_autoscaler(service_id)
            service_autoscaler(data, service_id, CHECK_INTERVAL)

            return jsonify({"message": f"Updated autoscaler for service {service_id}"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500


@scalerblp.route("/manual")
class HorizontalScaleManualyByCluster(MethodView):
    @scalerblp.arguments(ManualScaleFilterSchema(unknown=INCLUDE), location="json")
    def post(self, data, **kwargs):
        try:
            return manual_scale(data), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500


api.register_blueprint(scalerblp)

if __name__ == "__main__":
    login_to_system_manager()
    app.run(host="::", port=int(MY_PORT), debug=False)