import time
import cv2
from flask import Flask, render_template, jsonify, Response, request
from flask_socketio import SocketIO
from flask_cors import CORS

from firebase_config import FirebaseDB
from billing_engine import BillingEngine
from detection_engine import DetectionEngine

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Initialize components ─────────────────────────────────────
firebase_db = FirebaseDB()
billing = BillingEngine(firebase_db)

CAMERAS_CONFIG = [
    {"id": 1, "video": "cctv_1.mp4", "json": "bounding_boxes_1.json"},
    {"id": 2, "video": "cctv_2.mp4", "json": "bounding_boxes_2.json"},
]

detection = DetectionEngine(billing, socketio, CAMERAS_CONFIG)

# ── Page routes ────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/cctv")
def cctv():
    return render_template("cctv.html")

@app.route("/billing")
def billing_page():
    return render_template("billing.html")

# ── REST API ───────────────────────────────────────────────────

@app.route("/api/metrics")
def api_metrics():
    try:
        data = detection.get_metrics()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "capacity": 0, "occupied": 0, "empty": 0, "nearest_slot": None})

@app.route("/api/slots")
def api_slots():
    try:
        data = detection.get_slots()
        return jsonify(data)
    except Exception as e:
        return jsonify([])

@app.route("/api/transactions")
def api_transactions():
    try:
        return jsonify(billing.get_transactions())
    except Exception as e:
        return jsonify([])

@app.route("/api/activity")
def api_activity():
    try:
        return jsonify(billing.get_activity_logs())
    except Exception as e:
        return jsonify([])

@app.route("/api/billing/summary")
def api_billing_summary():
    try:
        return jsonify(billing.get_summary())
    except Exception as e:
        return jsonify({"total_cars_today": 0, "total_revenue_today": 0})

@app.route("/api/wallets")
def api_wallets():
    return jsonify(firebase_db.get_all_wallets())

@app.route("/api/wallet/<car_id>")
def api_wallet(car_id):
    balance = firebase_db.get_wallet_balance(car_id)
    return jsonify({"car_id": car_id, "balance": balance})

@app.route("/api/manual_entry", methods=["POST"])
def api_manual_entry():
    data = request.json
    plate = data.get("plate")
    if not plate:
        return jsonify({"error": "Plate is required"}), 400
    billing.manual_entered(plate)
    socketio.emit("car_entered")
    return jsonify({"success": True})

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.json
    plate = data.get("plate")
    if not plate:
        return jsonify({"error": "Plate is required"}), 400
    try:
        res = billing.manual_checkout(plate)
        socketio.emit("car_exited")
        return jsonify({"success": True, "bill": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/camera_health")
def api_camera_health():
    return jsonify(detection.get_health())

# ── MJPEG Video Stream ────────────────────────────────────────

def generate_frames(camera_id):
    """Generator for MJPEG stream."""
    while True:
        frame = detection.get_latest_frame(camera_id)
        if frame is not None:
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        else:
            # No frame yet — yield a placeholder
            placeholder = _create_placeholder_frame()
            ret, buffer = cv2.imencode(".jpg", placeholder)
            if ret:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        time.sleep(0.1)

def _create_placeholder_frame():
    """Create a dark placeholder frame when no video is available."""
    import numpy as np
    frame = np.zeros((600, 1080, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)
    cv2.putText(frame, "Connecting to camera...", (350, 290),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 2)
    cv2.putText(frame, "YOLO Detection Active", (380, 330),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 1)
    return frame

@app.route("/api/video_feed/<int:camera_id>")
def video_feed(camera_id):
    return Response(generate_frames(camera_id),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# ── WebSocket ──────────────────────────────────────────────────

@socketio.on("connect")
def handle_connect():
    print("[WS] Client connected")
    try:
        socketio.emit("slot_update", detection.get_slots())
    except Exception:
        pass

@socketio.on("disconnect")
def handle_disconnect():
    print("[WS] Client disconnected")

# ── Main ───────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  ParkFlow - Smart Parking Management System")
    print("=" * 50)
    print("  Dashboard : http://localhost:5000/")
    print("  CCTV      : http://localhost:5000/cctv")
    print("  Billing   : http://localhost:5000/billing")
    print("=" * 50 + "\n")

    # Start detection AFTER server starts (in background thread)
    import threading

    def start_detection_delayed():
        time.sleep(2)  # Give Flask time to fully start
        detection.start()

    det_thread = threading.Thread(target=start_detection_delayed, daemon=True)
    det_thread.start()

    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
