from flask import Flask, render_template, request, session, redirect, url_for, Response, jsonify
import cv2
import numpy as np
import csv
from datetime import datetime
from twilio.rest import Client
import os
import time
from flask_sqlalchemy import SQLAlchemy
from database import db, OTPVerification, DetectionLog
from detection import detect_objects, draw_detections

app = Flask(__name__)
app.secret_key = 'Salman@2002'

# ✅ DATABASE CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///animal_detection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# This block runs only when you run the file directly
with app.app_context():
    db.create_all()
    print("✅ created successfully.")

# ✅ Twilio Credentials
os.makedirs("logs", exist_ok=True)

# ---------------- LOGIN SYSTEM (OTP) ---------------- #
def send_otp(phone_number):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    otp = str(np.random.randint(100000, 999999))
    otp_store[phone_number] = otp

    # ✅ Save to database
    otp_entry = OTPVerification(phone_number=phone_number, otp=otp)
    db.session.add(otp_entry)
    db.session.commit()

    client.messages.create(
        body=f"Your OTP for login is: {otp}",
        from_=TWILIO_PHONE_NUMBER,
        to=phone_number
    )
    print(f"OTP sent to {phone_number}: {otp}")

def save_verified_user(phone):
    if not os.path.exists(VERIFIED_USERS_DB):
        with open(VERIFIED_USERS_DB, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["PhoneNumber"])
    with open(VERIFIED_USERS_DB, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([phone])

@app.route("/", methods=["GET", "POST"])
def index():
    return render_template("index.html")

@app.route("/send_otp", methods=["POST"])
def send_otp_request():
    data = request.get_json()
    phone = data.get("phone")

    if not phone:
        return jsonify({"error": "Phone number is required!"}), 400

    try:
        send_otp(phone)
        session["phone"] = phone
        return jsonify({"message": "OTP sent successfully!"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to send OTP: {e}")
        return jsonify({"error": "Failed to send OTP. Check phone number or Twilio setup."}), 500

@app.route("/verify", methods=["POST"])
def verify_otp():
    data = request.get_json()
    phone = session.get("phone")
    user_otp = data.get("otp")

    if not phone or not user_otp:
        return jsonify({"error": "Phone number or OTP missing!"}), 400

    latest_otp = OTPVerification.query.filter_by(phone_number=phone).order_by(OTPVerification.timestamp.desc()).first()

    if latest_otp and latest_otp.otp == user_otp:
        latest_otp.status = "verified"
        db.session.commit()
        
        session["logged_in"] = True
        session["verified_number"] = phone
        save_verified_user(phone)
        
        return jsonify({"message": "OTP Verified!"}), 200
    else:
        return jsonify({"error": "Invalid OTP!"}), 400

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------------- VIDEO STREAMING & DETECTION ---------------- #
def generate_frames(user_phone_number):
    global camera, is_detection_active
    while is_detection_active and camera is not None:
        success, frame = camera.read()
        if not success:
            print("Failed to read frame from camera!")
            break

        try:
            detections = detect_objects(frame)
            frame = draw_detections(frame, detections, user_phone_number)
        except Exception as e:
            print(f"Error in detection: {e}")
            break

        _, buffer = cv2.imencode('.jpg', frame)
        if not _:
            print("Failed to encode frame!")
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route("/start_detection", methods=["POST"])
def start_detection():
    global camera, is_detection_active
    if camera is None:
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            return jsonify({"error": "Failed to open camera!"}), 500
    is_detection_active = True
    return jsonify({"message": "Detection started!"})

@app.route("/stop_detection", methods=["POST"])
def stop_detection():
    global camera, is_detection_active
    is_detection_active = False
    if camera:
        camera.release()
        camera = None
    return jsonify({"message": "Detection stopped!"})

@app.route("/video_feed")
def video_feed():
    if not session.get("logged_in") or "verified_number" not in session:
        return redirect(url_for("index"))
    user_phone = session["verified_number"]
    return Response(generate_frames(user_phone), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("index"))
    return render_template("dashboard.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
