import os
from werkzeug.debug import DebuggedApplication
from werkzeug.serving import run_simple

from flask import Flask, jsonify
from flask.views import MethodView
from flask_swagger_ui import get_swaggerui_blueprint
from flask_smorest import Blueprint, Api
from marshmallow import INCLUDE, Schema, fields
from hca_logging import configure_logging
from helper import (
    get_hca_data_from_cluster,
    post_hca_monitor_data_to_cluster,
    delete_hca_monitor_data_from_cluster,
    put_hca_monitor_data_to_cluster,
    post_manual_scale_to_cluster
)
from other_requests import login_to_system_manager


MY_PORT = os.environ.get("MY_PORT", "10080")

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
    "horizontal autoscaler",
    "applications",
    url_prefix="/api/v1/hca",
    description="Operations on applications",
)

app.register_blueprint(swaggerui_blueprint)


class AutoscalerFilterSchema(Schema):
    """
    Schema for the autoscaler filter.
    """
    cpu_threshold = fields.Int()
    ram_threshold = fields.Int()
    min_replicas = fields.Int()
    max_replicas = fields.Int()

class ManualScaleFilterSchema(Schema):
    """
    Schema for the manual scale filter.
    """
    service_id = fields.String()
    cluster_id = fields.String(missing=None)
    scale_type = fields.String()  # up and down


@app.route("/")
def hello_world():
    return "Hello, World! This is the root_horizontal_autoscaler.\n"


@app.route("/status")
def status():
    return "ok"


@scalerblp.route("/<service_id>")
class HorizontalAutoscalerController(MethodView):
    def get(self, service_id):
        """
        Get the autoscaler data for a given service.
        """
        try:
            result = get_hca_data_from_cluster(service_id)
            return result, 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @scalerblp.arguments(AutoscalerFilterSchema(unknown=INCLUDE), location="json")
    def post(self, data, **kwargs):
        """
        Add an autoscaler for a given service.
        """
        service_id = kwargs.get("service_id")
        if get_hca_data_from_cluster(service_id):
            return jsonify({"error": "Autoscaler already exists"}), 400
        try:
            post_hca_monitor_data_to_cluster(service_id, data)
            return jsonify({"message": f"Adding autoscaler for service {service_id}"}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def delete(self, service_id):
        """
        Delete the autoscaler for a given service.
        """
        try:
            delete_hca_monitor_data_from_cluster(service_id)
            return jsonify({"message": f"Stopping autoscaler for service {service_id}"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @scalerblp.arguments(AutoscalerFilterSchema(unknown=INCLUDE), location="json")
    def put(self, data, service_id):
        """
        Update the autoscaler for a given service.
        """
        try:
            put_hca_monitor_data_to_cluster(service_id, data)
            return jsonify({"message": f"Updated autoscaler for service {service_id}"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500


@scalerblp.route("/manual")
class HorizontalScaleManualyByCluster(MethodView):
    @scalerblp.arguments(ManualScaleFilterSchema(unknown=INCLUDE), location="json")
    def post(self, data, **kwargs):
        """
        Scale a service manually by cluster.
        """
        try:
            response, status_code = post_manual_scale_to_cluster(data["service_id"], data)
            return response, status_code

        except Exception as e:
            return jsonify({"error": str(e)}), 500

api.register_blueprint(scalerblp)


if __name__ == "__main__":
    login_to_system_manager()
    app.run(host="::", port=int(MY_PORT), debug=True, use_reloader=True, use_debugger=False)
