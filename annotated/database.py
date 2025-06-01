from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class OTPVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), nullable=False)
    otp = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default="sent")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class DetectionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    animal_detected = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    frame_path = db.Column(db.String(255))
    alert_sent = db.Column(db.Boolean, default=False)
    user_phone = db.Column(db.String(15))
