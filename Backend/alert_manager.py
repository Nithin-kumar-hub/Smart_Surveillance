"""
alert_manager.py
Handles alert logic and notifications
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from datetime import datetime
import config


class AlertManager:
    """Manages alert notifications and external integrations"""
    
    def __init__(self, db, socketio):
        self.db = db
        self.socketio = socketio
        self.email_enabled = config.EMAIL_ENABLED
        self.webhook_url = config.WEBHOOK_URL
    
    def send_email_alert(self, alert_data):
        """Send email notification"""
        if not self.email_enabled:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = config.EMAIL_FROM
            msg['To'] = ', '.join(config.EMAIL_TO)
            msg['Subject'] = f"ALERT: {alert_data['object_class']} Detected"
            
            body = f"""
            Security Alert
            
            Camera: {alert_data['camera_name']}
            Location: {alert_data['location']}
            Object Detected: {alert_data['object_class']}
            Confidence: {alert_data['confidence'] * 100:.1f}%
            Severity: {alert_data['severity']}
            Time: {alert_data['timestamp']}
            
            Please check the dashboard for more details.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()
            # Note: Add authentication if needed
            # server.login(username, password)
            server.send_message(msg)
            server.quit()
            
            print(f"Email alert sent for {alert_data['object_class']}")
        
        except Exception as e:
            print(f"Failed to send email alert: {e}")
    
    def send_webhook_alert(self, alert_data):
        """Send alert to external webhook"""
        if not self.webhook_url:
            return
        
        try:
            response = requests.post(
                self.webhook_url,
                json=alert_data,
                timeout=5.0
            )
            
            if response.status_code == 200:
                print(f"Webhook alert sent successfully")
            else:
                print(f"Webhook returned status {response.status_code}")
        
        except Exception as e:
            print(f"Failed to send webhook alert: {e}")
    
    def process_alert(self, alert_data):
        """Process and dispatch alert through all channels"""
        # Send via WebSocket (real-time to dashboard)
        self.socketio.emit('new_alert', alert_data)
        
        # Send email if enabled
        if self.email_enabled:
            self.send_email_alert(alert_data)
        
        # Send webhook if configured
        if self.webhook_url:
            self.send_webhook_alert(alert_data)
        
        print(f"Alert processed: {alert_data['object_class']} at {alert_data['camera_name']}")
    
    def get_alert_statistics(self, hours=24):
        """Get alert statistics for reporting"""
        from datetime import timedelta
        
        start_time = datetime.now() - timedelta(hours=hours)
        
        alerts = self.db.get_alerts(pending_only=False, limit=1000)
        
        # Filter by time
        recent_alerts = [
            a for a in alerts 
            if datetime.fromisoformat(a['created_at']) >= start_time
        ]
        
        # Count by severity
        severity_counts = {
            'HIGH': 0,
            'MEDIUM': 0,
            'LOW': 0
        }
        
        for alert in recent_alerts:
            severity = alert.get('severity', 'LOW')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Count by type
        type_counts = {}
        for alert in recent_alerts:
            alert_type = alert.get('alert_type', 'Unknown')
            type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
        
        return {
            'total': len(recent_alerts),
            'by_severity': severity_counts,
            'by_type': type_counts,
            'pending': len([a for a in recent_alerts if not a['acknowledged']])
        }