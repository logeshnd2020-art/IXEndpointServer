from flask import Flask
from flask import request
from flask import jsonify
from services.device_service import get_device
from services.activity_service import activity_sync
from services.device_details_service import get_device_details
from flask import render_template

from database import initialize_database
from services.agent_service import (
    register_device,
    checkin_device,
    inventory_sync,
    application_sync
)
from services.fleet_service import get_all_devices

app = Flask(__name__)


@app.route("/")
def home():

    devices = get_all_devices()

    total = len(devices)

    online = sum(
        1 for d in devices
        if d["Status"] == "Online"
    )

    offline = total - online

    return render_template(
        "index.html",
        devices=devices,
        total=total,
        online=online,
        offline=offline
    )


@app.route("/api/agent/register", methods=["POST"])
def api_register():

    return jsonify(
        register_device(request.json)
    )
@app.route("/api/agent/checkin", methods=["POST"])
def api_checkin():

    return jsonify(
        checkin_device(request.json)
    )
@app.route("/device/<int:device_id>")
def device(device_id):

    details = get_device_details(device_id)
   
    return render_template(
        "device.html",
        details=details
    )
@app.route("/api/activity/events", methods=["POST"])
def api_activity_events():

    return jsonify(
        activity_sync(request.json)
    )
@app.route("/api/agent/inventory", methods=["POST"])
def api_inventory():

    return jsonify(
        inventory_sync(request.json)
    )
@app.route("/api/agent/applications", methods=["POST"])
def api_applications():

    return jsonify(
        application_sync(request.json)
    )
if __name__ == "__main__":

    initialize_database()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
