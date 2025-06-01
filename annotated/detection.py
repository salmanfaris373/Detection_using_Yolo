import cv2
import requests
import csv
from datetime import datetime, timedelta
from twilio.rest import Client
import os
from database import db, DetectionLog


# Roboflow API Setup
API_KEY = "XXXXXXXXXXXXXXXXX"
MODEL_ID = "XXXXXXXXXXXXXXXX"
API_URL = f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

# Twilio Credentials
TWILIO_ACCOUNT_SID = "XXXXXXXXXXXXXXXXXXXXxxxx"
TWILIO_AUTH_TOKEN = "XXXXXXXXXXXXXXXXXXXXX"
TWILIO_PHONE_NUMBER = "XXXXXXXXX"

log_file = "logs/detection_log.csv"
last_alert_times = {}

def get_geolocation():
    """Fetch approximate geolocation using an API."""
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        return data.get("loc", "Unknown")  # Format: "latitude,longitude"
    except:
        return "Unknown"

def send_alert(animal_name, user_phone_number):
    """Send an SMS alert using Twilio with geolocation and rate limiting."""
    global last_alert_times
    now = datetime.now()

    # Rate limit: Only send one alert per animal type per hour
    if animal_name in last_alert_times:
        time_since_last_alert = now - last_alert_times[animal_name]
        if time_since_last_alert < timedelta(hours=1):
            return  # Skip sending alert if less than an hour has passed

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    location = get_geolocation()
    message = f"Alert! {animal_name} detected at {now.strftime('%Y-%m-%d %H:%M:%S')}. Location: {location}."

    try:
        client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=user_phone_number)
        print(f"Alert sent for {animal_name}!")
        last_alert_times[animal_name] = now
    except Exception as e:
        print(f"Error sending alert: {e}")

def log_detection(animal_name, confidence):
    """Log the detection details to a CSV file with more information."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    location = get_geolocation()

    # Ensure logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    with open(log_file, "a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([now, animal_name, f"{confidence:.2f}", location])

def detect_objects(frame):
    """Send frame to Roboflow API for detection."""
    try:
        _, img_encoded = cv2.imencode(".jpg", frame)
        response = requests.post(API_URL, files={"file": img_encoded.tobytes()})
        return response.json()
    except Exception as e:
        print(f"Error during Roboflow detection: {e}")
        return {"predictions": []}

def draw_detections(frame, detections, user_phone_number):
    """Draw bounding boxes and labels on the frame."""
    predictions = detections.get("predictions", [])
    if not predictions:
        return frame  # No detections, skip

    # ✅ Save the current frame once
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    frame_filename = f"frame_{timestamp}.jpg"
    frame_path = os.path.join("static/detections", frame_filename)
    os.makedirs(os.path.dirname(frame_path), exist_ok=True)
    cv2.imwrite(frame_path, frame)

    for obj in predictions:
        x, y, w, h = obj["x"], obj["y"], obj["width"], obj["height"]
        label = obj["class"]
        confidence = obj["confidence"]

        # Draw rectangle and label
        cv2.rectangle(frame, 
                      (int(x - w / 2), int(y - h / 2)), 
                      (int(x + w / 2), int(y + h / 2)), 
                      (0, 255, 0), 2)

        label_text = f"{label} ({confidence:.2f})"
        cv2.putText(frame, label_text, 
                    (int(x), int(y - 10)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Send alert and log detection
        send_alert(label, user_phone_number)
        log_detection(label, confidence)
        log_detection_db(label, frame_path, user_phone_number)

    return frame

from flask import current_app

def log_detection_db(animal, frame_path, phone):
    from main2 import app  # import your Flask app instance
    with app.app_context():
        log = DetectionLog(
            animal_detected=animal,
            frame_path=frame_path,
            user_phone=phone,
            alert_sent=True
        )
        db.session.add(log)
        db.session.commit()
