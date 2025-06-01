import cv2
import requests
import numpy as np
import time
import csv
from datetime import datetime
from twilio.rest import Client
import winsound  # For detection sound (Windows)

# Roboflow API setup
API_KEY = "XXXXXXXXXXXXXx"
MODEL_ID = "XXXXXXXXXXXXXXXXXX"
API_URL = f"XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXxx"

# Twilio credentials
TWILIO_ACCOUNT_SID = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXxx"
TWILIO_AUTH_TOKEN = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_PHONE_NUMBER = "XXXXXXXXXXXXX"
USER_PHONE_NUMBER = "XXXXXXXXXXXXXXXx1"  # Updated User Phone Number

# Detection state variables
detection_count = 0
cooldown = False
log_file = "detection_log.csv"

def get_geolocation():
    """Fetch approximate geolocation using an API."""
    try:
        response = requests.get("https://ipinfo.io/json")
        data = response.json()
        location = data.get("loc", "Unknown")  # Format: "latitude,longitude"
        return location
    except Exception as e:
        print(f"Error fetching geolocation: {e}")
        return "Unknown"

def send_alert(animal_name):
    """Send an SMS alert using Twilio with geolocation."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    location = get_geolocation()
    message = f"Alert! {animal_name} detected at {now}. Location: {location}. Stay cautious."
    
    try:
        client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=USER_PHONE_NUMBER)
        print("Alert sent!")
    except Exception as e:
        print(f"Error sending alert: {e}")

def log_detection(animal_name, confidence):
    """Log the detection details to a CSV file."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    location = get_geolocation()
    with open(log_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([now, animal_name, confidence, location])
    print("Detection logged!")

def detect_objects(frame):
    """Send frame to Roboflow API for detection."""
    _, img_encoded = cv2.imencode('.jpg', frame)
    try:
        response = requests.post(API_URL, files={"file": img_encoded.tobytes()})
        return response.json()
    except Exception as e:
        print(f"Error in detection request: {e}")
        return {}

def draw_detections(frame, detections):
    """Draw bounding boxes and labels on the frame."""
    global detection_count, cooldown
    
    if cooldown:
        return frame  # Skip processing during cooldown

    detected = False
    
    for obj in detections.get("predictions", []):
        x, y, w, h = obj["x"], obj["y"], obj["width"], obj["height"]
        confidence, label = obj["confidence"], obj["class"]
        
        x1, y1, x2, y2 = int(x - w/2), int(y - h/2), int(x + w/2), int(y + h/2)
        
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"{label} ({confidence:.2f})", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        detected = True
        send_alert(label)
        log_detection(label, confidence)

        try:
            winsound.Beep(2000, 500)  # Windows only
        except Exception as e:
            print(f"Error playing beep sound: {e}")

        detection_count += 1
        if detection_count >= 2:
            print("Cooldown activated for 15 seconds...")
            cooldown = True
            detection_count = 0
            time.sleep(15)
            cooldown = False
            print("Detection resumed.")
    
    return frame

def main():
    cap = cv2.VideoCapture(0)  # Open webcam
    
    # Initialize CSV log file
    with open(log_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Animal Name", "Confidence Score", "Geolocation"])
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read from webcam.")
            break
        
        detections = detect_objects(frame)
        frame = draw_detections(frame, detections)
        
        cv2.imshow("Animal Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
