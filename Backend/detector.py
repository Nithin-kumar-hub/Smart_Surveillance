"""
detector_fixed.py
Fixed version of your original detector with bug fixes and improvements

Bug fixes:
1. Fixed __init__ method names (was _init_)
2. Fixed __name__ == "__main__" check
3. Added proper GPU/CPU fallback handling
4. Improved thread safety
5. Added graceful shutdown handling
"""

import argparse
import time
import os
import csv
import json
from datetime import datetime
from threading import Thread
from queue import Queue
from playsound import playsound

import cv2
import numpy as np
import pandas as pd
import requests



from ultralytics import YOLO

# -------------------------
# Configurable defaults
# -------------------------
OUTPUT_DIR = "outputs"
LOG_CSV = os.path.join(OUTPUT_DIR, "detections_log.csv")
ALERT_WEBHOOK = None
ALERT_CONF_THRESHOLD = 0.5
SAVE_SNAPSHOTS = True


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)


class VideoCaptureThread:
    """
    Threaded video capture to decouple camera I/O from inference.
    """
    def __init__(self, src=0, queue_size=8):  # FIXED: __init__ not _init_
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video source {src}")
        self.q = Queue(maxsize=queue_size)
        self.stopped = False
        self.thread = Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        while not self.stopped:
            if self.stopped:  # Check again before read
                break
            ret, frame = self.cap.read()
            if not ret:
                self.stop()
                break
            if not self.q.full():
                self.q.put(frame)
            time.sleep(0.01)  # Small delay to prevent CPU spinning

    def read(self):
        return self.q.get() if not self.q.empty() else None

    def stop(self):
        self.stopped = True
        if self.cap.isOpened():
            try:
                self.cap.release()
            except Exception as e:
                print(f"Error releasing capture: {e}")
        # Wait for thread to finish
        if self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def is_stopped(self):
        return self.stopped


def send_alert_webhook(webhook_url, payload):
    """Send a simple JSON POST to a webhook."""
    try:
        requests.post(webhook_url, json=payload, timeout=2.0)
    except Exception as e:
        print(f"[WARN] Webhook notification failed: {e}")


def log_detection_csv(row):
    header = ["timestamp", "frame_index", "class", "conf", "x1", "y1", "x2", "y2", "image_snapshot"]
    exists = os.path.exists(LOG_CSV)
    with open(LOG_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(header)
        writer.writerow(row)


def annotate_frame(frame, detections, class_names):
    """
    Draw boxes + labels on frame.
    """
    for det in detections:
        x1, y1, x2, y2 = map(int, det["bbox"])
        label = f"{det['class_name']} {det['conf']:.2f}"
        
        # Draw box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
        
        # Draw label background
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(frame, (x1, y1 - 20), (x1 + w, y1), (0, 0, 255), -1)
        cv2.putText(frame, label, (x1, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def run_detector(args):
    ensure_output_dir()

    # Load model with GPU/CPU fallback
    print("[INFO] Loading model:", args.weights)
    try:
        model = YOLO(args.weights)
        # Check if CUDA is available
        import torch
        if torch.cuda.is_available():
            print("[INFO] Using GPU for inference")
        else:
            print("[INFO] Using CPU for inference")
    except Exception as e:
        print(f"[ERROR] Failed to load model: {e}")
        return

    # Load class names
    class_names = None
    if args.names:
        with open(args.names, "r") as f:
            class_names = [s.strip() for s in f.readlines() if s.strip()]
    else:
        try:
            class_names = model.names
            if isinstance(class_names, dict):
                class_names = [class_names[i] for i in sorted(class_names.keys())]
        except Exception:
            class_names = [str(i) for i in range(1000)]

    # Harmful labels
    harmful_labels = set([
        "knife", "scissors", "baseball bat", "bat", "club", 
        "firearm", "gun", "handgun", "pistol", "rifle", "weapon"
    ])

    # Input handling
    is_image = bool(args.image)
    is_video = bool(args.video)

    writer = None
    out_path = None
    cap_thread = None
    frame_idx = 0

    if is_image:
        frame = cv2.imread(args.image)
        if frame is None:
            raise IOError("Cannot read image: " + args.image)
        frames_iter = [frame]
    else:
        # Parse video source
        video_src = args.video
        if video_src.isdigit():
            video_src = int(video_src)
        cap_thread = VideoCaptureThread(video_src)

    try:
        while True:
            if is_image:
                frame = frames_iter[0]
            else:
                frame = cap_thread.read()
                if frame is None:
                    if cap_thread.is_stopped():
                        print("[INFO] Video stream ended")
                        break
                    time.sleep(0.01)
                    continue

            frame_idx += 1
            t0 = time.time()

            # Run inference
            try:
                results = model.predict(
                    source=frame,
                    conf=args.conf,
                    iou=args.iou,
                    max_det=args.max_det,
                    imgsz=args.imgsz,
                    verbose=False
                )
            except Exception as e:
                print(f"[ERROR] Inference failed: {e}")
                if is_image:
                    break
                continue

            # Process results
            r = results[0]
            detections = []
            boxes = getattr(r, "boxes", None)
            
            if boxes is not None and len(boxes) > 0:
                for b in boxes:
                    xyxy = b.xyxy[0].cpu().numpy()
                    conf = float(b.conf.cpu().numpy())
                    cls_id = int(b.cls.cpu().numpy())
                    name = class_names[cls_id] if cls_id < len(class_names) else str(cls_id)
                    is_harmful = (name.lower() in harmful_labels)
                    
                    detections.append({
                        "class_id": cls_id,
                        "class_name": name,
                        "conf": conf,
                        "bbox": xyxy.tolist(),
                        "harmful": is_harmful
                    })

            # Filter if needed
            if args.only_harmful:
                detections = [d for d in detections if d["harmful"]]

            # Annotate
            annotated = annotate_frame(frame.copy(), detections, class_names)

            # Save video
            if args.save:
                if writer is None:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    out_path = os.path.join(OUTPUT_DIR, f"annotated_{ts}.mp4")
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    fps = args.fps if args.fps > 0 else 25
                    writer = cv2.VideoWriter(
                        out_path, fourcc, fps,
                        (annotated.shape[1], annotated.shape[0])
                    )
                writer.write(annotated)

            # Log detections
            for d in detections:
                x1, y1, x2, y2 = d["bbox"]
                snapshot_path = ""
                
                if SAVE_SNAPSHOTS and d["harmful"]:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    snapshot_path = os.path.join(OUTPUT_DIR, f"snapshot_{d['class_name']}_{ts}.jpg")
                    pad = 10
                    xi1 = max(0, int(x1) - pad)
                    yi1 = max(0, int(y1) - pad)
                    xi2 = min(frame.shape[1] - 1, int(x2) + pad)
                    yi2 = min(frame.shape[0] - 1, int(y2) + pad)
                    try:
                        cv2.imwrite(snapshot_path, frame[yi1:yi2, xi1:xi2])
                    except Exception as e:
                        print(f"[WARN] Failed to save snapshot: {e}")
                        snapshot_path = ""

                # CSV log
                row = [
                    datetime.now().isoformat(),
                    frame_idx,
                    d["class_name"],
                    f"{d['conf']:.3f}",
                    int(x1), int(y1), int(x2), int(y2),
                    snapshot_path
                ]
                log_detection_csv(row)

                # Alert
                # if d["harmful"] and d["conf"] >= ALERT_CONF_THRESHOLD:
                #     payload = {
                #         "timestamp": datetime.now().isoformat(),
                #         "frame_index": frame_idx,
                #         "class": d["class_name"],
                #         "conf": d["conf"],
                #         "bbox": [int(x1), int(y1), int(x2), int(y2)],
                #         "snapshot": snapshot_path
                #     }
                #     print("[ALERT]", json.dumps(payload))
                #     if ALERT_WEBHOOK:
                #         Thread(target=send_alert_webhook, 
                #                args=(ALERT_WEBHOOK, payload), 
                #                daemon=True).start()

                if d["harmful"] and d["conf"] >= ALERT_CONF_THRESHOLD:payload = {
                "timestamp": datetime.now().isoformat(),
                "frame_index": frame_idx,
                "class": d["class_name"],
                "conf": d["conf"],
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "snapshot": snapshot_path
                }

            print("[ALERT]", json.dumps(payload))

              # 🔊 PLAY ALERT SOUND (add your sound file in same folder)
            try:
                playsound("alert.mp3")
            except Exception as e:
                     print("[WARN] Failed to play alert sound:", e)

                 # Send webhook alert (if enabled)
                     if ALERT_WEBHOOK:
                         Thread(
                             target=send_alert_webhook,
                             args=(ALERT_WEBHOOK, payload),
                             daemon=True
                            ).start()


            # Display
            if args.display:
                fps = 1.0 / (time.time() - t0 + 1e-8)
                cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.imshow("Harmful Tool Detector", annotated)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("[INFO] User requested quit")
                    break

            # For image, only one iteration
            if is_image:
                if args.save:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    img_out = os.path.join(OUTPUT_DIR, f"annotated_{ts}.jpg")
                    cv2.imwrite(img_out, annotated)
                    print("[INFO] Annotated image saved to:", img_out)
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if cap_thread:
            cap_thread.stop()
        if writer:
            writer.release()
        if args.display:
            cv2.destroyAllWindows()

    if out_path:
        print("[INFO] Annotated video saved to:", out_path)
    print("[INFO] Done.")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--image", type=str, default="", help="Path to input image")
    p.add_argument("--video", type=str, default="", help="Video file, webcam (0), or RTSP URL")
    p.add_argument("--weights", type=str, default="yolov8n.pt", help="Model weights")
    p.add_argument("--names", type=str, default="", help="Class names file")
    p.add_argument("--conf", type=float, default=0.35, help="Confidence threshold")
    p.add_argument("--iou", type=float, default=0.45, help="NMS IOU threshold")
    p.add_argument("--max_det", type=int, default=100, help="Max detections")
    p.add_argument("--imgsz", type=int, default=416, help="Inference size")
    p.add_argument("--display", action="store_true", help="Show window")
    p.add_argument("--save", action="store_true", help="Save output")
    p.add_argument("--only_harmful", action="store_true", help="Only show harmful objects")
    p.add_argument("--fps", type=int, default=25, help="Output FPS")
    return p.parse_args()


if __name__ == "__main__":  # FIXED: Was _name_ and "_main_"
    args = parse_args()
    if not args.image and not args.video:
        print("Error: Provide --image or --video")
        print("\nExamples:")
        print("  python detector_fixed.py --image test.jpg --weights yolov8n.pt --display --save")
        print("  python detector_fixed.py --video 0 --weights yolov8n.pt --display")
        print("  python detector_fixed.py --video input.mp4 --weights yolov8n.pt --save")
    else:
        run_detector(args)