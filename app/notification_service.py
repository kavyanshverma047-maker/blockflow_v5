# app/notification_service.py
from datetime import datetime
import random

notifications = []

def push_notification(user: str, msg: str, level="info"):
    notif = {
        "user": user,
        "message": msg,
        "level": level,
        "timestamp": datetime.utcnow().isoformat()
    }
    notifications.append(notif)
    return notif

def get_notifications(user: str):
    return [n for n in notifications if n["user"] == user]
