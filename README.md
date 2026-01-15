# Smart-Surveillance

Smart-Surveillance is a real-time CCTV monitoring system that detects weapons in video feeds and sends instant alerts to administrators. It is intended to help security teams detect potentially dangerous situations faster by combining object detection, video streaming, and alerting mechanisms.

---

Table of contents
- Features
- Example / Demo
- Requirements
- Quick start
- Running (common workflows)
- Model / Data
- Alerting & Notifications
- Troubleshooting
- Contributing
- Contact

---

Features
- Real-time weapon detection on live CCTV / RTSP / webcam streams
- Lightweight detection model compatible with GPU and CPU
- Configurable alerting: email, SMS, webhook, push notification (placeholders)
- Saves detected frames and logs for audit and review
- Easy-to-run scripts and Docker support
- Extensible: swap detection model or add new alert handlers

Example / Demo
- Provide a short GIF or screenshot here (e.g., `docs/demo.gif`) showing detection bounding boxes and alerts.
- Example: "A weapon is detected in the top-left area — an alert is sent and the frame is saved to `alerts/`."

Requirements
- Python 3.8+ (recommended)
- GPU with CUDA (optional, for faster inference)
- Dependencies (install via requirements file):
  - OpenCV (cv2)
  - PyTorch or TensorFlow (depending on chosen detection model)
  - numpy, requests, pyyaml (and other utilities)
    
Quick start (local)
1. Clone the repository:
   ```
   git clone https://github.com/Nithin-kumar-hub/Smart_Surveillance.git
   cd Smart_Surveillance
   ```
2. Create virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate        # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   If there is no `requirements.txt` add the dependencies manually or create one from environment.

3. Download or place detection model weights:
   - Put weights in `models/` and name them appropriately, e.g. `models/weapon_detector.pt`
   - Replace `<MODEL_WEIGHTS>` below with the actual path.

4. Run the detector against a webcam, file or RTSP stream (example):
   ```
   python <DETECT_SCRIPT>.py --weights models/weapon_detector.pt --source 0
   ```
   Examples of `--source`:
   - `0` — system webcam
   - `path/to/video.mp4` — video file
   - `rtsp://user:pass@camera-ip:554/stream` — network camera

Running (common workflows)
- Watch a single camera:
  ```
  python <DETECT_SCRIPT>.py --source rtsp://... --weights models/weapon_detector.pt --save-frames
  ```
- Run in headless server mode (no GUI) and enable alerts:
  ```
  python <DETECT_SCRIPT>.py --source rtsp://... --weights models/weapon_detector.pt --headless --alerts enabled
  ```
- Batch process recorded footage:
  ```
  python <DETECT_SCRIPT>.py --source /path/to/folder --weights models/weapon_detector.pt --output results/
  ```

Model / Data
- Detection model: (e.g., YOLOv5/YOLOv8, Faster R-CNN, or custom)
- Expected input/annotation format: COCO / YOLO / Pascal VOC — update the documentation to match the dataset used.
- Pretrained weights: include a pointer to where weights can be downloaded, or include instructions for training below.


Alerting & Notifications
- Supported alert channels: email, webhook, SMS (via provider), push notifications.
- Example webhook payload:
  ```json
  {
    "timestamp": "2026-01-15T12:34:56Z",
    "camera": "Front Gate",
    "label": "weapon",
    "confidence": 0.92,
    "image_url": "https://server/alerts/frame_123.jpg"
  }
  ```
- Configure alerting in `config.yml` (or the configuration file used in this repo). Typical fields:
  - webhook_url
  - email_smtp (host, port, username, password, recipients)
  - sms_provider (api_key, from_number)


Troubleshooting
- Low detection accuracy:
  - Check dataset quality and annotation correctness
  - Fine-tune model on target domain (same camera angles / resolution)
- High CPU usage / slow inference:
  - Use GPU-backed inference, optimize model (prune, quantize), reduce image resolution
- No alerts sent:
  - Verify network connectivity and webhook/email credentials
  - Check logs in `logs/` or standard output for error traces

Contributing
- Contributions welcome! Please follow these steps:
  1. Fork the repository
  2. Create a feature branch: `git checkout -b feature/my-feature`
  3. Commit changes and push
  4. Open a pull request describing the change and rationale
- Please include tests for new features and update documentation.

Security & Privacy
- Handle camera credentials and alerting credentials securely (do not commit them)
- Follow applicable laws and policies before deploying surveillance systems in public/private spaces


Contact
- For issues and feature requests, open an issue on this repository.
- For direct contact: replace with project maintainer email or GitHub profile: [Nithin-kumar-hub](https://github.com/Nithin-kumar-hub)

---
