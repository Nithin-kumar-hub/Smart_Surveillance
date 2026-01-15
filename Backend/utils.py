"""
utils.py
Utility functions for timezone handling
"""

from datetime import datetime
import pytz

def get_ist_time():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

def format_ist_time(dt):
    """Format datetime to IST ISO string"""
    if dt.tzinfo is None:
        # Assume UTC and convert to IST
        utc = pytz.timezone('UTC')
        dt = utc.localize(dt)
    
    ist = pytz.timezone('Asia/Kolkata')
    return dt.astimezone(ist).isoformat()