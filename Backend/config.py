"""
config.py
Configuration settings for Smart Surveillance System
"""

import os

# ==================
# SERVER SETTINGS
# ==================
HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 5000
DEBUG = False  # Set to False in production
SECRET_KEY = '8bd94d77c38faef38fa83b1feaf3e4928a69c6e006b6e363f6ad8ea9578f2f2b'

# ==================
# PATHS
# ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'outputs')
SNAPSHOTS_DIR = os.path.join(OUTPUT_DIR, 'snapshots')
VIDEOS_DIR = os.path.join(OUTPUT_DIR, 'videos')
LOG_DIR = os.path.join(OUTPUT_DIR, 'logs')

# Database
DB_PATH = os.path.join(BASE_DIR, '..', 'data', 'surveillance.db')

# Model
MODEL_PATH = os.path.join(BASE_DIR, '..', 'models', 'yolov8n.pt')
# For custom trained model, use:
MODEL_PATH = os.path.join(BASE_DIR, '..', 'models', 'best (1).pt')

# ==================
# DETECTION SETTINGS
# ==================
# YOLO Parameters
CONFIDENCE_THRESHOLD = 0.70  # Min confidence to consider detection (balanced)
IOU_THRESHOLD = 0.45         # Non-maximum suppression threshold
MAX_DETECTIONS = 100         # Max detections per frame
INFERENCE_SIZE = 640         # Input size for YOLO (320, 416, or 640)
ALERT_CONFIDENCE_THRESHOLD = 0.75  # Send alerts for confident detections

# Add minimum detection area (prevents tiny false detections)
MIN_DETECTION_AREA = 3000  # pixels (balanced size)
                             # Lower = faster but less accurate
                             # 416 is good balance for low-spec machines

# Performance Optimization
FRAME_SKIP = 8               # Process every 8th frame (balanced speed and accuracy)
RESIZE_DIMENSION = 640       # Resize frame width before processing (None to disable)

# Harmful Object Classes
# These should match your model's class names
HARMFUL_CLASSES = [
    'baseball bat',
    'crow bar',
    'hammer',
    'knife',
    'pistol',
    'rifle'
]

# ==================
# ALERT SETTINGS
# ==================
ALERT_CONFIDENCE_THRESHOLD = 0.5  # Min confidence to send alert
ALERT_COOLDOWN = 30                # Seconds between alerts for same class
SAVE_SNAPSHOTS = True              # Save detection snapshots

# Alert Severity Thresholds
SEVERITY_HIGH = 0.8     # Confidence >= 0.8 = HIGH severity
SEVERITY_MEDIUM = 0.6   # Confidence >= 0.6 = MEDIUM severity
                        # Below 0.6 = LOW severity

# ==================
# STREAMING SETTINGS
# ==================
STREAM_QUALITY = 90     # JPEG quality (1-100, higher = better quality but more bandwidth)
STREAM_FPS = 30         # Target FPS for video streams

# ==================
# DATABASE SETTINGS
# ==================
# Auto-cleanup old data (optional)
AUTO_CLEANUP_ENABLED = True
CLEANUP_DAYS = 30       # Delete detections older than N days

# ==================
# NOTIFICATION SETTINGS
# ==================
# Email notifications (optional - implement if needed)
EMAIL_ENABLED = False
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_FROM = 'alerts@surveillance.com'
EMAIL_TO = ['admin@surveillance.com']

# Webhook URL for external alerts (optional)
WEBHOOK_URL = None  # Set to URL if you want to send alerts to external service

# ==================
# LOGGING SETTINGS
# ==================
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_TO_FILE = True
LOG_FILE = os.path.join(LOG_DIR, 'surveillance.log')

# ==================
# CAMERA DEFAULTS
# ==================
DEFAULT_CAMERA_FPS = 60
DEFAULT_CAMERA_RESOLUTION = (640, 640)

# ==================
# DEVELOPMENT/TESTING
# ==================
DEMO_MODE = False  # Enable to use test images/videos instead of live cameras
TEST_VIDEO_PATH = os.path.join(BASE_DIR, '..', 'tests', 'test_video.mp4')


# ==================
# AUTO-CREATE DIRECTORIES
# ==================
def ensure_directories():
    """Create necessary directories if they don't exist"""
    dirs = [OUTPUT_DIR, SNAPSHOTS_DIR, VIDEOS_DIR, LOG_DIR]
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)
    
    # Create models and data directories
    models_dir = os.path.join(BASE_DIR, '..', 'models')
    data_dir = os.path.join(BASE_DIR, '..', 'data')
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)


if __name__ == '__main__':
    ensure_directories()
    print("Configuration loaded successfully")
    print(f"Model path: {MODEL_PATH}")
    print(f"Database path: {DB_PATH}")
    print(f"Output directory: {OUTPUT_DIR}")