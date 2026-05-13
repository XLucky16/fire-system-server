from flask import Flask, render_template, jsonify
import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)

EMAIL_SENDER   = "abdelrahmanassem597@gmail.com"
EMAIL_PASSWORD = "kpjwmzuyqodstqid"
EMAIL_RECEIVER = "M.Mohamed27124@student.aast.edu"

state_lock = threading.Lock()

system_state = {
    "fire_detected":        False,
    "timer_started_at":     0,
    "authorities_notified": False,
    "time_left":            30
}

incident_log = []

MQTT_BROKER   = "broker.hivemq.com"
MQTT_PORT     = 1883
TOPIC_RECEIVE = "ece4302/fire_group/status"
TOPIC_SEND    = "ece4302/fire_group/commands"

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

def send_emergency_email():
    try:
        msg = MIMEText(
            "🚨 URGENT: Fire Detected at Node 1!\n\n"
            "The local admin did not respond within 30 seconds.\n"
            "Please dispatch emergency services immediately."
        )
        msg["Subject"] = "IoT System Alert: FIRE ESCALATION"
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)

        print("✅ EMERGENCY EMAIL SENT SUCCESSFULLY!")
    except Exception as e:
        print(f"❌ Email not sent ({e}). Check your sender email and password.")

def log_event(event_description: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with state_lock:
        incident_log.insert(0, {"time": timestamp, "event": event_description})

def _reset_state():
    system_state["fire_detected"]        = False
    system_state["authorities_notified"] = False
    system_state["time_left"]            = 30
    system_state["timer_started_at"]     = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("\n✅ Connected to MQTT Broker successfully!\n")
        client.subscribe(TOPIC_RECEIVE)
    else:
        print(f"❌ MQTT connection failed with code {rc}")

def on_message(client, userdata, msg):
    message = msg.payload.decode().strip()

    if msg.topic == TOPIC_RECEIVE and message == "FIRE":
        with state_lock:
            if not system_state["fire_detected"]:
                system_state["fire_detected"]    = True
                system_state["timer_started_at"] = time.time()
                system_state["authorities_notified"] = False
        log_event("🔥 Fire Detected! Sprinklers Activated.")
        print("🔥 Fire signal received — countdown started.")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def start_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"❌ Could not connect to MQTT broker: {e}")

threading.Thread(target=start_mqtt, daemon=True).start()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    with state_lock:
        if system_state["fire_detected"] and not system_state["authorities_notified"]:
            elapsed   = time.time() - system_state["timer_started_at"]
            remaining = max(0, 30 - int(elapsed))
            system_state["time_left"] = remaining

            if remaining == 0:
                system_state["authorities_notified"] = True
                threading.Thread(target=send_emergency_email, daemon=True).start()
                do_log = True
            else:
                do_log = False

        snapshot = {
            "state": dict(system_state),
            "logs":  list(incident_log)
        }

    if "do_log" in dir() and do_log:
        log_event("🚨 Escalated: Authorities Notified via Email.")

    return jsonify(snapshot)

@app.route("/api/dismiss")
def dismiss_alarm():
    with state_lock:
        _reset_state()
    mqtt_client.publish(TOPIC_SEND, "SAFE")
    log_event("✅ Alarm Dismissed by Admin.")
    return jsonify({"status": "success"})

@app.route("/api/reset")
def reset_system():
    with state_lock:
        _reset_state()
        incident_log.clear()
    mqtt_client.publish(TOPIC_SEND, "SAFE")
    log_event("🔄 System Reset by Admin.")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    log_event("💻 System Booted Up.")
    # التعديل هنا لكي يعمل على Render أو محلياً بدون مشاكل
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)