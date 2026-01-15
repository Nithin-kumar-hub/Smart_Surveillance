"""
camera_manager.py
Handles multiple camera streams and detection processing
Place this file in: backend/camera_manager.py
"""

import cv2
import numpy as np
from threading import Thread, Lock
from queue import Queue, Empty
import time
from datetime import datetime
from ultralytics import YOLO
import os

import config


class CameraThread:
    """Individual camera processing thread"""
    
    def __init__(self, camera_id, source, model, db, socketio):
        self.camera_id = camera_id
        self.source = source if source != '0' else 0  # Convert '0' string to int
        self.model = model
        self.db = db
        self.socketio = socketio
        
        self.cap = None
        self.stopped = False
        self.latest_frame = None
        self.frame_lock = Lock()
        
        self.frame_count = 0
        self.detection_count = 0
        self.last_alert_time = {}  # Track last alert per class
        self.detection_history = {}  # Track recent detections for consistency check
        
        # Performance optimization
        self.frame_skip = config.FRAME_SKIP  # Process every Nth frame
        self.resize_dim = config.RESIZE_DIMENSION
        
        # Harmful object classes
        self.harmful_classes = set([label.lower() for label in config.HARMFUL_CLASSES])
        
        self.thread = Thread(target=self._process_stream, daemon=True)
    
    def start(self):
        """Start camera thread"""
        # Reset state
        self.stopped = False
        self.frame_count = 0
        self.detection_count = 0
        self.last_alert_time.clear()
        self.detection_history.clear()
        self.latest_frame = None
        
        # Open camera with DirectShow backend (better for Windows)
        if isinstance(self.source, int):
            # For webcam, use DirectShow backend on Windows
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            print(f"[INFO] Opening camera {self.camera_id} with DirectShow backend")
        else:
            # For RTSP/video files, use default backend
            self.cap = cv2.VideoCapture(self.source)
            print(f"[INFO] Opening camera {self.camera_id} from source: {self.source}")
        
        if not self.cap.isOpened():
            raise IOError(f"Cannot open camera {self.camera_id} at {self.source}")
        
        # Set camera properties for better performance
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Allow camera to warm up and verify it works
        print(f"[INFO] Camera {self.camera_id} warming up...")
        warmup_success = False
        for i in range(30):
            ret, frame = self.cap.read()
            if ret and frame is not None:
                warmup_success = True
                if i >= 10:  # After 10 successful reads, we're good
                    break
        
        if not warmup_success:
            self.cap.release()
            raise IOError(f"Camera {self.camera_id} failed to produce valid frames during warmup")
        
        self.thread.start()
        print(f"[INFO] Camera {self.camera_id} started successfully")
    
    def _process_stream(self):
        """Main processing loop"""
        consecutive_failures = 0
        consecutive_invalid = 0
        max_failures = 10
        max_invalid = 300  # Allow more invalid frames before stopping
        
        while not self.stopped:
            try:
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures % 10 == 1:  # Log every 10th failure
                        print(f"[WARN] Camera {self.camera_id}: Failed to read frame ({consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        print(f"[ERROR] Camera {self.camera_id}: Too many consecutive failures, stopping")
                        self.stopped = True
                        break
                    
                    time.sleep(0.5)
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                # Validate frame (but be lenient during startup)
                is_valid = self._is_valid_frame(frame)
                
                if not is_valid:
                    consecutive_invalid += 1
                    
                    # During startup (first 100 frames), be more lenient
                    if self.frame_count < 100:
                        # Just log once at the very beginning
                        if self.frame_count == 1 and consecutive_invalid == 1:
                            print(f"[INFO] Camera {self.camera_id}: Warming up, some initial frames may be invalid...")
                        # Still store and process the frame
                        is_valid = True
                    else:
                        # After startup, be strict
                        if consecutive_invalid == 1:
                            print(f"[WARN] Camera {self.camera_id}: Receiving invalid frames (camera may be off or covered)")
                        elif consecutive_invalid >= max_invalid:
                            print(f"[ERROR] Camera {self.camera_id}: Too many invalid frames, camera may be disconnected")
                            self.stopped = True
                            break
                        
                        # Still store the frame for streaming (so user can see black screen)
                        with self.frame_lock:
                            self.latest_frame = frame.copy()
                        
                        time.sleep(0.1)
                        continue
                
                # Reset invalid counter on valid frame
                if is_valid and consecutive_invalid > 0:
                    if consecutive_invalid > 10:
                        print(f"[INFO] Camera {self.camera_id}: Receiving valid frames again")
                    consecutive_invalid = 0
                
                self.frame_count += 1
                
                # Process detection only if camera is stable
                annotated_frame = frame.copy()
                if self.frame_count > 30:  # Skip first 30 frames for camera stabilization
                    # Skip frames for performance
                    if self.frame_count % self.frame_skip == 0:
                        annotated_frame = self._detect_objects(frame)
                
                # Store latest annotated frame for streaming
                with self.frame_lock:
                    self.latest_frame = annotated_frame
                
            except Exception as e:
                print(f"[ERROR] Camera {self.camera_id} error: {e}")
                consecutive_failures += 1
                time.sleep(1)
    
    def _is_valid_frame(self, frame):
        """Validate frame quality to prevent false detections"""
        if frame is None:
            return False
        
        # Check frame dimensions
        if len(frame.shape) < 2 or frame.shape[0] < 50 or frame.shape[1] < 50:
            return False
        
        # Check if frame is not completely black (camera off)
        # More lenient threshold - allow darker frames
        mean_intensity = np.mean(frame)
        if mean_intensity < 1:  # Only reject completely black frames
            return False
        
        # Check if frame has some variance (not a completely uniform frame)
        # More lenient threshold
        std_dev = np.std(frame)
        if std_dev < 2:  # Very low variance indicates blank/uniform frame
            return False
        
        return True
    
    def _detect_objects(self, frame):
        """Run YOLO detection on frame and return annotated frame"""
        annotated_frame = frame.copy()
        
        try:
            # Resize for faster inference
            if self.resize_dim:
                h, w = frame.shape[:2]
                if w > self.resize_dim:
                    scale = self.resize_dim / w
                    new_w = self.resize_dim
                    new_h = int(h * scale)
                    input_frame = cv2.resize(frame, (new_w, new_h))
                    scale_factor = w / new_w
                else:
                    input_frame = frame
                    scale_factor = 1.0
            else:
                input_frame = frame
                scale_factor = 1.0
            
            # Run inference
            results = self.model.predict(
                source=input_frame,
                conf=config.CONFIDENCE_THRESHOLD,
                iou=config.IOU_THRESHOLD,
                max_det=config.MAX_DETECTIONS,
                imgsz=config.INFERENCE_SIZE,
                verbose=False
            )
            
            # Process results
            if results and len(results) > 0:
                r = results[0]
                boxes = getattr(r, 'boxes', None)
                
                if boxes is not None and len(boxes) > 0:
                    annotated_frame = self._process_detections(frame, boxes, scale_factor)
            
        except Exception as e:
            print(f"[ERROR] Detection error for camera {self.camera_id}: {e}")
        
        return annotated_frame
    
    def _process_detections(self, frame, boxes, scale_factor):
        """Process detection results and return annotated frame"""
        annotated_frame = frame.copy()
        
        try:
            class_names = self.model.names
            
            for box in boxes:
                # Extract box information
                xyxy = box.xyxy[0].cpu().numpy()
                conf = float(box.conf.cpu().numpy())
                cls_id = int(box.cls.cpu().numpy())
                
                # Scale back to original frame size
                x1, y1, x2, y2 = (xyxy * scale_factor).astype(int)
                
                # Validate bounding box
                if not self._is_valid_bbox(x1, y1, x2, y2, frame.shape):
                    continue
                
                # Calculate detection area
                detection_area = (x2 - x1) * (y2 - y1)
                if detection_area < config.MIN_DETECTION_AREA:
                    print(f"[DEBUG] Skipping small detection: {detection_area} pixels")
                    continue
                
                # Get class name
                class_name = class_names[cls_id] if cls_id < len(class_names) else str(cls_id)
                
                # Check if harmful
                is_harmful = class_name.lower() in self.harmful_classes
                
                # ONLY process harmful objects - ignore everything else
                if not is_harmful:
                    continue
                
                # Draw bounding box only for harmful detections
                if is_harmful:
                    # Red box for harmful objects
                    color = (0, 0, 255)  # BGR: Red
                    thickness = 3
                else:
                    # Green box for non-harmful objects
                    color = (0, 255, 0)  # BGR: Green
                    thickness = 2
                
                # Draw rectangle
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, thickness)
                
                # Prepare label text
                label = f"{class_name} {conf:.2f}"
                
                # Get text size for background
                (text_width, text_height), baseline = cv2.getTextSize(
                    label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                )
                
                # Draw label background
                cv2.rectangle(
                    annotated_frame,
                    (x1, y1 - text_height - 10),
                    (x1 + text_width + 10, y1),
                    color,
                    -1  # Filled rectangle
                )
                
                # Draw label text
                cv2.putText(
                    annotated_frame,
                    label,
                    (x1 + 5, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),  # White text
                    2,
                    cv2.LINE_AA
                )
                
                # Process harmful detections
                if is_harmful:
                    self.detection_count += 1
                    
                    # Save snapshot with full frame and bounding box
                    snapshot_path = self._save_snapshot(
                        annotated_frame, x1, y1, x2, y2, class_name, conf
                    )
                    
                    # Log to database
                    detection_id = self.db.log_detection(
                        camera_id=self.camera_id,
                        object_class=class_name,
                        confidence=conf,
                        bbox=[int(x1), int(y1), int(x2), int(y2)],
                        snapshot_path=snapshot_path
                    )
                    
                    # Check if alert should be sent
                    if self._should_send_alert(class_name, conf):
                        self._send_alert(detection_id, class_name, conf, snapshot_path)
        
        except Exception as e:
            print(f"[ERROR] Process detections error: {e}")
        
        return annotated_frame
    
    def _is_valid_bbox(self, x1, y1, x2, y2, frame_shape):
        """Validate bounding box coordinates"""
        h, w = frame_shape[:2]
        
        # Check if coordinates are within frame
        if x1 < 0 or y1 < 0 or x2 > w or y2 > h:
            return False
        
        # Check if box has valid dimensions
        if x2 <= x1 or y2 <= y1:
            return False
        
        # Check if box is not too large (likely false detection)
        box_area = (x2 - x1) * (y2 - y1)
        frame_area = w * h
        if box_area > frame_area * 0.9:  # Box covers more than 90% of frame
            return False
        
        # Ignore detections too close to frame edges (often false positives)
        edge_margin = 30  # pixels from edge (balanced)
        if x1 < edge_margin or y1 < edge_margin or x2 > (w - edge_margin) or y2 > (h - edge_margin):
            return False
        
        return True
    
    def _save_snapshot(self, annotated_frame, x1, y1, x2, y2, class_name, conf):
        """Save detection snapshot - full frame with bounding box and person"""
        try:
            # Create a copy of the annotated frame for snapshot
            snapshot_frame = annotated_frame.copy()
            
            # Add additional context text at the top
            h, w = snapshot_frame.shape[:2]
            
            # Add timestamp and camera info
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            camera_info = f"Camera {self.camera_id} | {timestamp_str}"
            
            # Draw semi-transparent background for text
            overlay = snapshot_frame.copy()
            cv2.rectangle(overlay, (0, 0), (w, 40), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, snapshot_frame, 0.4, 0, snapshot_frame)
            
            # Add camera info text
            cv2.putText(
                snapshot_frame,
                camera_info,
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            
            # Add alert banner at bottom
            alert_text = f"ALERT: {class_name.upper()} DETECTED - Confidence: {conf:.1%}"
            (text_w, text_h), _ = cv2.getTextSize(
                alert_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
            )
            
            # Draw alert banner
            banner_y = h - 50
            cv2.rectangle(
                snapshot_frame,
                (0, banner_y),
                (w, h),
                (0, 0, 255),
                -1
            )
            
            # Add alert text
            text_x = (w - text_w) // 2
            cv2.putText(
                snapshot_frame,
                alert_text,
                (text_x, banner_y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )
            
            # Save full frame with annotations
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"cam{self.camera_id}_{class_name}_{timestamp}.jpg"
            filepath = os.path.join(config.SNAPSHOTS_DIR, filename)
            
            cv2.imwrite(filepath, snapshot_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"[INFO] Snapshot saved: {filename}")
            return filepath
        
        except Exception as e:
            print(f"[ERROR] Save snapshot error: {e}")
            return ""
    
    def _should_send_alert(self, class_name, confidence):
        """Determine if alert should be sent with consistency check"""
        # Check confidence threshold
        if confidence < config.ALERT_CONFIDENCE_THRESHOLD:
            print(f"[DEBUG] Alert skipped: confidence {confidence:.2f} below threshold {config.ALERT_CONFIDENCE_THRESHOLD}")
            return False
        
        # Check if camera is in stable state (not just started/stopped)
        # Wait for camera to stabilize
        if self.frame_count < 120:
            print(f"[DEBUG] Alert skipped: camera still stabilizing (frame {self.frame_count}/120)")
            return False
        
        # Consistency check: Track recent detections
        current_time = time.time()
        if class_name not in self.detection_history:
            self.detection_history[class_name] = []
        
        # Add current detection
        self.detection_history[class_name].append(current_time)
        
        # Remove old detections (older than 3 seconds)
        self.detection_history[class_name] = [
            t for t in self.detection_history[class_name] 
            if current_time - t < 3
        ]
        
        # Require at least 3 detections within 3 seconds before alerting (balanced)
        if len(self.detection_history[class_name]) < 3:
            print(f"[DEBUG] Alert skipped: not enough consistent detections ({len(self.detection_history[class_name])}/3)")
            return False
        
        # Check alert cooldown
        if class_name in self.last_alert_time:
            time_since_last = current_time - self.last_alert_time[class_name]
            if time_since_last < config.ALERT_COOLDOWN:
                print(f"[DEBUG] Alert skipped: cooldown active ({time_since_last:.1f}s / {config.ALERT_COOLDOWN}s)")
                return False
        
        self.last_alert_time[class_name] = current_time
        print(f"[INFO] Alert approved: {class_name} detected consistently with {confidence:.2f} confidence")
        return True
    
    def _send_alert(self, detection_id, class_name, confidence, snapshot_path):
        """Send alert notification"""
        try:
            # Determine severity
            if confidence > 0.8:
                severity = "HIGH"
            elif confidence > 0.6:
                severity = "MEDIUM"
            else:
                severity = "LOW"
            
            # Create alert
            alert_id = self.db.create_alert(
                detection_id=detection_id,
                camera_id=self.camera_id,
                alert_type=class_name,
                severity=severity
            )
            
            # Get camera info
            camera = self.db.get_camera(self.camera_id)
            
            # Prepare alert data
            alert_data = {
                'alert_id': alert_id,
                'camera_id': self.camera_id,
                'camera_name': camera['name'],
                'location': camera['location'],
                'object_class': class_name,
                'confidence': round(confidence, 3),
                'severity': severity,
                'timestamp': datetime.now().isoformat(),
                'snapshot': snapshot_path
            }
            
            # Emit via WebSocket
            self.socketio.emit('new_alert', alert_data)
            
            print(f"[ALERT] Camera {self.camera_id}: {class_name} detected ({confidence:.2f})")
        
        except Exception as e:
            print(f"[ERROR] Send alert error: {e}")
    
    def get_latest_frame(self):
        """Get the latest frame"""
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def stop(self):
        """Stop camera thread"""
        print(f"[INFO] Stopping camera {self.camera_id}...")
        self.stopped = True
        
        # Clear alert history to prevent false alerts on restart
        self.last_alert_time.clear()
        self.detection_history.clear()
        
        # Release camera
        if self.cap:
            try:
                self.cap.release()
            except Exception as e:
                print(f"[WARN] Error releasing camera {self.camera_id}: {e}")
        
        # Wait for thread to finish
        if self.thread.is_alive():
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                print(f"[WARN] Camera {self.camera_id} thread did not stop gracefully")
        
        print(f"[INFO] Camera {self.camera_id} stopped")


class CameraManager:
    """Manages multiple camera threads"""
    
    def __init__(self, db, socketio):
        self.db = db
        self.socketio = socketio
        self.cameras = {}
        self.cameras_lock = Lock()
        
        # Don't open a camera here - it blocks other processes from using it
        # self.Video = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        
        # Load YOLO model once (shared across all cameras)
        print(f"[INFO] Loading YOLO model: {config.MODEL_PATH}")
        try:
            self.model = YOLO(config.MODEL_PATH)
            print("[INFO] Model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load model: {e}")
            raise
    
    def start_camera(self, camera_id):
        """Start a camera"""
        with self.cameras_lock:
            if camera_id in self.cameras:
                print(f"[WARN] Camera {camera_id} already running")
                return
            
            # Get camera source from database
            camera_info = self.db.get_camera(camera_id)
            if not camera_info:
                raise ValueError(f"Camera {camera_id} not found in database")
            
            source = camera_info['rtsp_url']
            
            # Convert string '0' to integer 0 for webcam
            if source == '0':
                source = 0
            
            # Test if camera is accessible before creating thread
            print(f"[INFO] Testing camera {camera_id} accessibility...")
            test_cap = None
            try:
                if isinstance(source, int):
                    test_cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
                else:
                    test_cap = cv2.VideoCapture(source)
                
                if not test_cap.isOpened():
                    raise IOError(f"Camera {camera_id} is not accessible. It may be in use by another application.")
                
                # Try to read a frame
                ret, frame = test_cap.read()
                if not ret or frame is None:
                    raise IOError(f"Camera {camera_id} cannot capture frames. Check camera permissions.")
                
                print(f"[INFO] Camera {camera_id} is accessible")
                
            finally:
                if test_cap is not None:
                    test_cap.release()
                    time.sleep(0.5)  # Give time for camera to be released
            
            # Create and start camera thread
            try:
                camera_thread = CameraThread(
                    camera_id=camera_id,
                    source=source,
                    model=self.model,
                    db=self.db,
                    socketio=self.socketio
                )
                
                camera_thread.start()
                self.cameras[camera_id] = camera_thread
                
                print(f"[INFO] Camera {camera_id} started successfully")
            except Exception as e:
                print(f"[ERROR] Failed to start camera {camera_id}: {e}")
                raise
    
    def stop_camera(self, camera_id):
        """Stop a camera"""
        with self.cameras_lock:
            if camera_id in self.cameras:
                self.cameras[camera_id].stop()
                del self.cameras[camera_id]
                print(f"[INFO] Camera {camera_id} stopped")
    
    def stop_all_cameras(self):
        """Stop all cameras"""
        with self.cameras_lock:
            for camera_id in list(self.cameras.keys()):
                self.cameras[camera_id].stop()
            self.cameras.clear()
            print("[INFO] All cameras stopped")
    
    def get_latest_frame(self, camera_id):
        """Get latest frame from camera"""
        with self.cameras_lock:
            if camera_id in self.cameras:
                return self.cameras[camera_id].get_latest_frame()
        return None
    
    def get_active_count(self):
        """Get number of active cameras"""
        with self.cameras_lock:
            return len(self.cameras)
    
    def get_status(self):
        """Get status of all cameras"""
        with self.cameras_lock:
            status = []
            for camera_id, camera_thread in self.cameras.items():
                status.append({
                    'camera_id': camera_id,
                    'running': not camera_thread.stopped,
                    'frame_count': camera_thread.frame_count,
                    'detection_count': camera_thread.detection_count
                })
            return status
    
    def is_camera_running(self, camera_id):
        """Check if camera is running"""
        with self.cameras_lock:
            return camera_id in self.cameras and not self.cameras[camera_id].stopped
    
    def get_camera_stats(self, camera_id):
        """Get statistics for a specific camera"""
        with self.cameras_lock:
            if camera_id in self.cameras:
                cam = self.cameras[camera_id]
                return {
                    'camera_id': camera_id,
                    'frame_count': cam.frame_count,
                    'detection_count': cam.detection_count,
                    'running': not cam.stopped
                }
        return None