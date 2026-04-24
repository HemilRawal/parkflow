import cv2
import numpy as np
import json
import time
import threading
import os
import traceback
from datetime import datetime


class DetectionEngine:
    """Processes video feeds with YOLO, tracks slot occupancy, detects improper parking."""

    def __init__(self, billing_engine, socketio, cameras_config):
        self.billing = billing_engine
        self.socketio = socketio
        self.cameras_config = cameras_config
        self.slots_by_cam = {}  # {cam_id: {slot_id: points}}
        self.latest_frames = {}
        self.camera_health = {}
        self.running = False
        self.car_counter = 0
        self.lock = threading.Lock()
        self.model = None  # Lazy load
        self.DEBOUNCE_FRAMES = 5  # Frames a slot must be empty before car is considered "left"
        self.empty_frame_counts = {}  # slot_id -> consecutive empty frame count
        self.slot_states = {}

        self._load_all_slots()

    def _load_all_slots(self):
        for cam in self.cameras_config:
            cam_id = cam["id"]
            bbox_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", cam["json"])
            bbox_path = os.path.normpath(bbox_path)
            print(f"[Detection] Loading slots for CAM-{cam_id} from: {bbox_path}")
            
            with open(bbox_path) as f:
                data = json.load(f)

            slots = {}
            for i, region in enumerate(data[:3]):
                slot_id = f"C{cam_id}-A-{str(i + 1).zfill(2)}"
                slots[slot_id] = region["points"]
            for i, region in enumerate(data[3:]):
                slot_id = f"C{cam_id}-B-{str(i + 1).zfill(2)}"
                slots[slot_id] = region["points"]
                
            self.slots_by_cam[cam_id] = slots
            
            for slot_id in slots:
                self.slot_states[slot_id] = {
                    "status": "empty",
                    "car_id": None,
                    "timer_start": None,
                    "is_improper": False,
                }
                self.empty_frame_counts[slot_id] = 0
                
            print(f"[Detection] Loaded {len(slots)} parking slots for CAM-{cam_id}")

    def _load_model(self):
        """Lazy-load YOLO model in the detection thread."""
        if self.model is None:
            from ultralytics import YOLO
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "yolo11s.pt")
            model_path = os.path.normpath(model_path)
            print(f"[Detection] Loading YOLO model from: {model_path}")
            self.model = YOLO(model_path)
            print("[Detection] YOLO model loaded successfully")

    def _assign_car_id(self):
        self.car_counter += 1
        return f"CAR-{str(self.car_counter).zfill(4)}"

    def _check_improper_parking(self, car_box, slot_points):
        """Returns True if car is improperly parked.
        Uses slot coverage: what fraction of the slot is covered by the car.
        If the car covers less than 15% of the slot area, it's improper."""
        try:
            from shapely.geometry import Polygon, box as shapely_box
            x1, y1, x2, y2 = car_box
            car_poly = shapely_box(float(x1), float(y1), float(x2), float(y2))
            slot_poly = Polygon(slot_points)
            if not slot_poly.is_valid or not car_poly.is_valid:
                return False
            intersection = car_poly.intersection(slot_poly)
            # How much of the slot is covered by the car
            slot_coverage = intersection.area / slot_poly.area if slot_poly.area > 0 else 0
            # If the car covers less than 15% of the slot, it's improper
            return slot_coverage < 0.15
        except Exception as e:
            print(f"[Detection] IoA check error: {e}")
            return False

    def process_video(self, video_path, camera_id):
        try:
            with self.lock:
                self._load_model()
        except Exception as e:
            print(f"[Detection] Failed to load YOLO model: {e}")
            traceback.print_exc()
            return

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"[Detection] ERROR: Cannot open video: {video_path}")
            return

        print(f"[Detection] Processing {video_path} as Camera {camera_id}")
        frame_count = 0
        cam_slots = self.slots_by_cam[camera_id]

        while cap.isOpened() and self.running:
            ret, frame = cap.read()
            if not ret:
                print(f"[Detection] Video ended for CAM-{camera_id} after {frame_count} frames")
                self._handle_video_end(camera_id)
                # Loop video for continuous processing in demo
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame = cv2.resize(frame, (1080, 600))
            frame_count += 1

            # Camera Health Check (Black footage detection)
            mean_val = np.mean(frame)
            current_health = 0 if mean_val < 20 else 100
            
            with self.lock:
                if self.camera_health.get(camera_id, 100) != current_health:
                    self.camera_health[camera_id] = current_health
                    if current_health == 0:
                        print(f"[Health] CAM-{camera_id} offline (Black footage detected)")
                        log = {
                            "type": "system_alert",
                            "camera_id": camera_id,
                            "alert": f"Camera {camera_id} Offline (Signal Lost)",
                            "timestamp": datetime.now().strftime("%I:%M %p"),
                            "time_ago": "Just now"
                        }
                        self.billing.activity_logs.insert(0, log)
                        self.billing.db.add_activity(log)
                        
                        # Set slots to offline
                        for slot_id in cam_slots.keys():
                            self.slot_states[slot_id] = {
                                "status": "offline", "car_id": None,
                                "timer_start": None, "is_improper": False,
                            }
                        self.socketio.emit("slot_update", self.get_slots_unlocked())
                        
                    else:
                        print(f"[Health] CAM-{camera_id} back online")
                        # Set offline slots back to empty
                        for slot_id in cam_slots.keys():
                            if self.slot_states[slot_id]["status"] == "offline":
                                self.slot_states[slot_id] = {
                                    "status": "empty", "car_id": None,
                                    "timer_start": None, "is_improper": False,
                                }
                        self.socketio.emit("slot_update", self.get_slots_unlocked())
                    
                    self.socketio.emit("health_update", self.camera_health)

            if current_health == 0:
                # Skip YOLO detection if camera is broken
                self.latest_frames[camera_id] = frame.copy()
                continue

            try:
                results = self.model(frame, classes=[2], verbose=False)
            except Exception as e:
                print(f"[Detection] YOLO inference error: {e}")
                continue

            detected_boxes = []
            if len(results) > 0 and results[0].boxes is not None:
                for box_data in results[0].boxes:
                    detected_boxes.append(box_data.xyxy[0].cpu().numpy())

            current_occupied = set()

            with self.lock:
                for slot_id, slot_points in cam_slots.items():
                    pts_array = np.array(slot_points, dtype=np.int32).reshape((-1, 1, 2))

                    for car_box in detected_boxes:
                        xc = int((car_box[0] + car_box[2]) / 2)
                        yc = int((car_box[1] + car_box[3]) / 2)
                        dist = cv2.pointPolygonTest(pts_array, (xc, yc), False)

                        if dist >= 0:
                            current_occupied.add(slot_id)
                            self.empty_frame_counts[slot_id] = 0  # Reset debounce
                            prev = self.slot_states[slot_id]

                            if prev["status"] == "empty":
                                car_id = self._assign_car_id()
                                is_improper = self._check_improper_parking(car_box, slot_points)

                                self.slot_states[slot_id] = {
                                    "status": "occupied",
                                    "car_id": car_id,
                                    "timer_start": time.time(),
                                    "is_improper": is_improper,
                                }
                                print(f"[Detection] Car {car_id} entered slot {slot_id} {'(IMPROPER)' if is_improper else ''}")

                                self.billing.car_entered(car_id, slot_id, is_improper)
                                try:
                                    self.socketio.emit("slot_update", self.get_slots_unlocked())
                                    self.socketio.emit("car_entered", {
                                        "car_id": car_id, "slot_id": slot_id,
                                        "is_improper": is_improper,
                                    })
                                except Exception:
                                    pass
                            break

                # Cars that left — with debounce
                for slot_id in list(cam_slots.keys()):
                    state = self.slot_states[slot_id]
                    if state["status"] == "occupied" and slot_id not in current_occupied:
                        self.empty_frame_counts[slot_id] = self.empty_frame_counts.get(slot_id, 0) + 1
                        # Only mark as left after DEBOUNCE_FRAMES consecutive empty frames
                        if self.empty_frame_counts[slot_id] >= self.DEBOUNCE_FRAMES:
                            car_id = state["car_id"]
                            duration = time.time() - state["timer_start"]
                            print(f"[Detection] Car {car_id} exited slot {slot_id} after {duration:.1f}s")

                            bill = self.billing.car_exited(car_id, slot_id, duration, state["is_improper"])

                            self.slot_states[slot_id] = {
                                "status": "empty", "car_id": None,
                                "timer_start": None, "is_improper": False,
                            }
                            self.empty_frame_counts[slot_id] = 0
                            try:
                                self.socketio.emit("slot_update", self.get_slots_unlocked())
                                self.socketio.emit("car_exited", {
                                    "car_id": car_id, "slot_id": slot_id, "bill": bill,
                                })
                            except Exception:
                                pass

            annotated = self._annotate_frame(frame, camera_id)
            self.latest_frames[camera_id] = annotated

            if frame_count % 30 == 0:
                occ = sum(1 for sid in cam_slots if self.slot_states[sid]["status"] == "occupied")
                print(f"[Detection] CAM-{camera_id} Frame {frame_count} | Occupied: {occ}/{len(cam_slots)}")

            time.sleep(0.03)

        cap.release()
        print(f"[Detection] Video processing complete for CAM-{camera_id}")

    def _annotate_frame(self, frame, camera_id):
        annotated = frame.copy()
        cam_slots = self.slots_by_cam[camera_id]
        
        for slot_id, slot_points in cam_slots.items():
            pts = np.array(slot_points, dtype=np.int32).reshape((-1, 1, 2))
            state = self.slot_states[slot_id]

            if state["status"] == "occupied":
                color = (0, 165, 255) if state["is_improper"] else (0, 0, 255)
            else:
                color = (0, 255, 0)

            cv2.polylines(annotated, [pts], True, color, 2)
            center = np.mean(slot_points, axis=0).astype(int)
            cv2.putText(annotated, slot_id, (center[0] - 25, center[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        return annotated

    def _handle_video_end(self, camera_id):
        """When video ends, assume all parked cars left."""
        cam_slots = self.slots_by_cam[camera_id]
        with self.lock:
            for slot_id in cam_slots.keys():
                state = self.slot_states[slot_id]
                if state["status"] == "occupied":
                    car_id = state["car_id"]
                    duration = time.time() - state["timer_start"]
                    print(f"[Detection] Video ended - billing car {car_id} in {slot_id} for {duration:.1f}s")
                    bill = self.billing.car_exited(car_id, slot_id, duration, state["is_improper"])

                    self.slot_states[slot_id] = {
                        "status": "empty", "car_id": None,
                        "timer_start": None, "is_improper": False,
                    }
                    try:
                        self.socketio.emit("car_exited", {
                            "car_id": car_id, "slot_id": slot_id, "bill": bill,
                        })
                    except Exception:
                        pass
            try:
                self.socketio.emit("slot_update", self.get_slots_unlocked())
                self.socketio.emit("video_ended", {"camera_id": camera_id})
            except Exception:
                pass

    # ── Public API (thread-safe) ────────────────────────────

    def get_slots_unlocked(self):
        """Call only when lock is already held."""
        return [
            {"id": sid, "status": s["status"], "car_id": s["car_id"],
             "is_improper": s["is_improper"], "timer_start": s["timer_start"]}
            for sid, s in self.slot_states.items()
        ]

    def get_metrics(self):
        with self.lock:
            occupied = sum(1 for s in self.slot_states.values() if s["status"] == "occupied")
            empty = sum(1 for s in self.slot_states.values() if s["status"] == "empty")
            offline = sum(1 for s in self.slot_states.values() if s["status"] == "offline")
            total = len(self.slot_states)
            nearest = None
            for sid in sorted(self.slot_states.keys()):
                if self.slot_states[sid]["status"] == "empty":
                    nearest = sid
                    break
            return {"capacity": total, "occupied": occupied,
                    "empty": empty, "offline": offline, "nearest_slot": nearest}

    def get_slots(self):
        with self.lock:
            return self.get_slots_unlocked()

    def get_latest_frame(self, camera_id):
        return self.latest_frames.get(camera_id)

    def get_health(self):
        with self.lock:
            return self.camera_health.copy()

    def start(self):
        self.running = True
        
        for cam in self.cameras_config:
            video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", cam["video"])
            video_path = os.path.normpath(video_path)
            cam_id = cam["id"]
            
            print(f"[Detection] Starting detection thread for CAM-{cam_id}: {video_path}")
            t = threading.Thread(target=self.process_video, args=(video_path, cam_id), daemon=True)
            t.start()

    def stop(self):
        self.running = False
