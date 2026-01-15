"""
database.py
SQLite database operations for surveillance system
"""

import sqlite3
from datetime import datetime, timedelta
from threading import Lock
import json

import pytz
from datetime import datetime,timezone



class Database:
    """Database handler with thread-safe operations"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = Lock()
        self.conn = None
    
    def _get_connection(self):
        """Get thread-local database connection"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def initialize(self):
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Cameras table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                rtsp_url TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Detections table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                object_class TEXT NOT NULL,
                confidence REAL,
                bbox_x1 INTEGER,
                bbox_y1 INTEGER,
                bbox_x2 INTEGER,
                bbox_y2 INTEGER,
                snapshot_path TEXT,
                alert_sent BOOLEAN DEFAULT 0,
                FOREIGN KEY (camera_id) REFERENCES cameras (id)
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detection_id INTEGER,
                camera_id INTEGER,
                alert_type TEXT,
                severity TEXT,
                message TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                acknowledged_by TEXT,
                acknowledged_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (detection_id) REFERENCES detections (id),
                FOREIGN KEY (camera_id) REFERENCES cameras (id)
            )
        ''')
        
        # Analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                hour INTEGER,
                camera_id INTEGER,
                object_class TEXT,
                detection_count INTEGER,
                FOREIGN KEY (camera_id) REFERENCES cameras (id)
            )
        ''')
        
        conn.commit()
        print("Database initialized successfully")
    
    # ==================
    # CAMERA OPERATIONS
    # ==================
    
    def add_camera(self, name, location='', rtsp_url='0'):
        """Add a new camera"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO cameras (name, location, rtsp_url)
                VALUES (?, ?, ?)
            ''', (name, location, rtsp_url))
            conn.commit()
            return cursor.lastrowid
    
    def get_camera(self, camera_id):
        """Get camera by ID"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cameras WHERE id = ?', (camera_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_cameras(self):
        """Get all cameras"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM cameras ORDER BY id')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def update_camera_status(self, camera_id, status):
        """Update camera status"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE cameras SET status = ? WHERE id = ?
            ''', (status, camera_id))
            conn.commit()
    
    def delete_camera(self, camera_id):
        """Delete a camera"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM cameras WHERE id = ?', (camera_id,))
            conn.commit()
    
    # =====================
    # DETECTION OPERATIONS
    # =====================
    
    def log_detection(self, camera_id, object_class, confidence, bbox, snapshot_path=''):
        """Log a detection"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            ist = pytz.timezone('Asia/Kolkata')
            timestamp = datetime.now(ist)
            cursor.execute('''
                INSERT INTO detections (
                    camera_id, object_class, confidence,
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2, snapshot_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (camera_id, object_class, confidence,
                  bbox[0], bbox[1], bbox[2], bbox[3], snapshot_path))
            conn.commit()
            
            # Update analytics
            self._update_analytics(camera_id, object_class)
            
            return cursor.lastrowid
    
    def get_detections(self, camera_id=None, limit=50, offset=0, start_date=None, end_date=None):
        """Get detections with filters"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = '''
                SELECT d.*, c.name as camera_name, c.location
                FROM detections d
                JOIN cameras c ON d.camera_id = c.id
                WHERE 1=1
            '''
            params = []
            
            if camera_id:
                query += ' AND d.camera_id = ?'
                params.append(camera_id)
            
            if start_date:
                query += ' AND d.timestamp >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND d.timestamp <= ?'
                params.append(end_date)
            
            query += ' ORDER BY d.timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # =================
    # ALERT OPERATIONS
    # =================
    
    # def create_alert(self, detection_id, camera_id, alert_type, severity):
    #     """Create an alert"""
    #     with self.lock:
    #         conn = self._get_connection()
    #         cursor = conn.cursor()
            
    #         message = f"{alert_type} detected with {severity} severity"
    #         ist = pytz.timezone('Asia/Kolkata')
    #         created_at = datetime.now(ist)
    #         cursor.execute('''
    #             INSERT INTO alerts (
    #                 detection_id, camera_id, alert_type, severity, message
    #             ) VALUES (?, ?, ?, ?, ?)
    #         ''', (detection_id, camera_id, alert_type, severity, message))
            
    #         # Mark detection as alerted
    #         cursor.execute('''
    #             UPDATE detections SET alert_sent = 1 WHERE id = ?
    #         ''', (detection_id,))
            
    #         conn.commit()
    #         return cursor.lastrowid
    def create_alert(self, detection_id, camera_id, alert_type, severity):
        """Create an alert"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            message = f"{alert_type} detected with {severity} severity"

            # FIX: Convert UTC → IST and store real IST timestamp
            ist = pytz.timezone('Asia/Kolkata')
            created_at = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                INSERT INTO alerts (
                    detection_id, camera_id, alert_type, severity, message, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (detection_id, camera_id, alert_type, severity, message, created_at))

            # Mark detection as alerted
            cursor.execute('''
                UPDATE detections SET alert_sent = 1 WHERE id = ?
            ''', (detection_id,))

            conn.commit()
            return cursor.lastrowid

    
    def get_alerts(self, pending_only=True, limit=100):
        """Get alerts"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = '''
                SELECT a.*, c.name as camera_name, c.location,
                       d.object_class, d.confidence, d.snapshot_path
                FROM alerts a
                JOIN cameras c ON a.camera_id = c.id
                JOIN detections d ON a.detection_id = d.id
            '''
            
            if pending_only:
                query += ' WHERE a.acknowledged = 0'
            
            query += ' ORDER BY a.created_at DESC LIMIT ?'
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def acknowledge_alert(self, alert_id, admin_name):
        """Acknowledge an alert"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE alerts
                SET acknowledged = 1,
                    acknowledged_by = ?,
                    acknowledged_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (admin_name, alert_id))
            conn.commit()
    
    # =====================
    # ANALYTICS OPERATIONS
    # =====================
    
    def _update_analytics(self, camera_id, object_class):
        """Update hourly analytics"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        now = datetime.now()
        date = now.date()
        hour = now.hour
        
        # Check if record exists
        cursor.execute('''
            SELECT id, detection_count FROM analytics
            WHERE date = ? AND hour = ? AND camera_id = ? AND object_class = ?
        ''', (date, hour, camera_id, object_class))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing
            cursor.execute('''
                UPDATE analytics
                SET detection_count = detection_count + 1
                WHERE id = ?
            ''', (row['id'],))
        else:
            # Insert new
            cursor.execute('''
                INSERT INTO analytics (date, hour, camera_id, object_class, detection_count)
                VALUES (?, ?, ?, ?, 1)
            ''', (date, hour, camera_id, object_class))
        
        conn.commit()
    
    def get_analytics_summary(self, start_time):
        """Get analytics summary"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total detections
            cursor.execute('''
                SELECT COUNT(*) as total FROM detections
                WHERE timestamp >= ?
            ''', (start_time,))
            total = cursor.fetchone()['total']
            
            # By class
            cursor.execute('''
                SELECT object_class, COUNT(*) as count
                FROM detections
                WHERE timestamp >= ?
                GROUP BY object_class
                ORDER BY count DESC
            ''', (start_time,))
            by_class = [dict(row) for row in cursor.fetchall()]
            
            # By camera
            cursor.execute('''
                SELECT c.name, COUNT(d.id) as count
                FROM detections d
                JOIN cameras c ON d.camera_id = c.id
                WHERE d.timestamp >= ?
                GROUP BY c.name
                ORDER BY count DESC
            ''', (start_time,))
            by_camera = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_detections': total,
                'by_class': by_class,
                'by_camera': by_camera
            }
    
    def get_hourly_analytics(self, camera_id, hours=24):
        """Get hourly analytics data"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            query = '''
                SELECT
                    strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                    object_class,
                    COUNT(*) as count
                FROM detections
                WHERE timestamp >= ?
            '''
            params = [start_time]
            
            if camera_id:
                query += ' AND camera_id = ?'
                params.append(camera_id)
            
            query += ' GROUP BY hour, object_class ORDER BY hour'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_detection_heatmap(self, camera_id, hours=24):
        """Get detection heatmap data (bbox centers)"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute('''
                SELECT
                    (bbox_x1 + bbox_x2) / 2 as x,
                    (bbox_y1 + bbox_y2) / 2 as y,
                    object_class
                FROM detections
                WHERE camera_id = ? AND timestamp >= ?
            ''', (camera_id, start_time))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None