"""
app.py
Flask Backend API for Smart Surveillance System

Endpoints:
- GET  /api/cameras              - List all cameras
- POST /api/cameras              - Add new camera
- GET  /api/cameras/<id>/stream  - Get camera stream
- GET  /api/detections           - Get recent detections
- GET  /api/alerts               - Get pending alerts
- POST /api/alerts/<id>/ack      - Acknowledge alert
- GET  /api/analytics            - Get analytics data
- WebSocket /socket              - Real-time updates
"""

from flask import Flask, request, jsonify, Response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
# import eventlet
# eventlet.monkey_patch()

import cv2
import json
import os
from datetime import datetime, timedelta
from threading import Thread, Lock
import time

from database import Database
from camera_manager import CameraManager
from alert_manager import AlertManager
import config

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize components
db = Database(config.DB_PATH)
camera_manager = CameraManager(db, socketio)
alert_manager = AlertManager(db, socketio)

# Global state
active_streams = {}
streams_lock = Lock()


# ===========================
# REST API ENDPOINTS
# ===========================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cameras_active': camera_manager.get_active_count()
    })


@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """Get all registered cameras"""
    try:
        cameras = db.get_all_cameras()
        return jsonify({
            'success': True,
            'cameras': cameras
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras', methods=['POST'])
def add_camera():
    """Add a new camera"""
    try:
        data = request.json
        camera_id = db.add_camera(
            name=data['name'],
            location=data.get('location', ''),
            rtsp_url=data.get('rtsp_url', '0')  # 0 for webcam
        )
        
        # Start camera detection
        camera_manager.start_camera(camera_id)
        
        return jsonify({
            'success': True,
            'camera_id': camera_id,
            'message': 'Camera added successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
def remove_camera(camera_id):
    """Remove a camera"""
    try:
        camera_manager.stop_camera(camera_id)
        db.delete_camera(camera_id)
        return jsonify({
            'success': True,
            'message': 'Camera removed successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cameras/<int:camera_id>/toggle', methods=['POST'])
def toggle_camera(camera_id):
    """Start/Stop camera detection"""
    try:
        action = request.json.get('action', 'stop')
        if action == 'start':
            camera_manager.start_camera(camera_id)
        else:
            camera_manager.stop_camera(camera_id)
        
        return jsonify({
            'success': True,
            'action': action,
            'message': f'Camera {action}ed successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def generate_frames(camera_id):
    """Generator for video streaming"""
    while True:
        try:
            frame = camera_manager.get_latest_frame(camera_id)
            if frame is not None:
                # Encode frame to JPEG
                success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if success:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    print(f"[WARN] Failed to encode frame for camera {camera_id}")
            else:
                # If no frame available, wait a bit longer
                time.sleep(0.1)
                continue
            
            time.sleep(0.033)  # ~30 FPS
        except GeneratorExit:
            # Client disconnected
            print(f"[INFO] Client disconnected from camera {camera_id} stream")
            break
        except Exception as e:
            print(f"[ERROR] Stream error for camera {camera_id}: {e}")
            time.sleep(0.5)
            # Don't break, try to continue streaming


@app.route('/api/cameras/<int:camera_id>/stream')
def video_stream(camera_id):
    """Stream video from camera"""
    return Response(
        generate_frames(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/detections', methods=['GET'])
def get_detections():
    """Get recent detections with filters"""
    try:
        # Query parameters
        camera_id = request.args.get('camera_id', type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        detections = db.get_detections(
            camera_id=camera_id,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'success': True,
            'detections': detections,
            'count': len(detections)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get alerts (pending or all)"""
    try:
        pending_only = request.args.get('pending', 'true').lower() == 'true'
        limit = request.args.get('limit', 100, type=int)
        
        alerts = db.get_alerts(pending_only=pending_only, limit=limit)
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        data = request.json
        admin_name = data.get('admin_name', 'Admin')
        
        db.acknowledge_alert(alert_id, admin_name)
        
        # Notify all clients
        socketio.emit('alert_acknowledged', {
            'alert_id': alert_id,
            'acknowledged_by': admin_name,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({
            'success': True,
            'message': 'Alert acknowledged'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/summary', methods=['GET'])
def get_analytics_summary():
    """Get analytics summary"""
    try:
        # Time range
        hours = request.args.get('hours', 24, type=int)
        start_time = datetime.now() - timedelta(hours=hours)
        
        summary = db.get_analytics_summary(start_time)
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/hourly', methods=['GET'])
def get_hourly_analytics():
    """Get hourly detection statistics"""
    try:
        camera_id = request.args.get('camera_id', type=int)
        hours = request.args.get('hours', 24, type=int)
        
        data = db.get_hourly_analytics(camera_id, hours)
        
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/heatmap', methods=['GET'])
def get_detection_heatmap():
    """Get detection heatmap data"""
    try:
        camera_id = request.args.get('camera_id', type=int, required=True)
        hours = request.args.get('hours', 24, type=int)
        
        heatmap_data = db.get_detection_heatmap(camera_id, hours)
        
        return jsonify({
            'success': True,
            'heatmap': heatmap_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================
# WEBSOCKET EVENTS
# ===========================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f"Client connected: {request.sid}")
    emit('connection_response', {
        'status': 'connected',
        'timestamp': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")


@socketio.on('subscribe_camera')
def handle_subscribe(data):
    """Subscribe to camera updates"""
    camera_id = data.get('camera_id')
    print(f"Client {request.sid} subscribed to camera {camera_id}")
    # Join room for camera-specific updates
    from flask_socketio import join_room
    join_room(f'camera_{camera_id}')


@socketio.on('request_status')
def handle_status_request():
    """Send system status to client"""
    status = {
        'cameras': camera_manager.get_status(),
        'pending_alerts': len(db.get_alerts(pending_only=True)),
        'timestamp': datetime.now().isoformat()
    }
    emit('status_update', status)


# ===========================
# STARTUP & SHUTDOWN
# ===========================

def initialize_system():
    """Initialize system on startup"""
    print("=" * 50)
    print("Smart Surveillance System Starting...")
    print("=" * 50)
    
    # Create necessary directories
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    os.makedirs(config.SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(config.VIDEOS_DIR, exist_ok=True)
    
    # Initialize database
    db.initialize()
    
    # Load and start cameras from config
    cameras = db.get_all_cameras()
    for camera in cameras:
        if camera['status'] == 'active':
            try:
                camera_manager.start_camera(camera['id'])
                print(f"Started camera: {camera['name']}")
            except Exception as e:
                print(f"Failed to start camera {camera['name']}: {e}")
    
    print("System initialized successfully!")
    print("=" * 50)


def shutdown_system():
    """Cleanup on shutdown"""
    print("\nShutting down surveillance system...")
    camera_manager.stop_all_cameras()
    db.close()
    print("System shutdown complete.")


if __name__ == '__main__':
    try:
        initialize_system()
        
        # Run Flask app
        socketio.run(
            app,
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=False,  # Prevent double initialization
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        shutdown_system()
    except Exception as e:
        print(f"Fatal error: {e}")
        shutdown_system()