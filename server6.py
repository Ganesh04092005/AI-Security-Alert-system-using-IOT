from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import requests
import cv2
import os
import pickle
import numpy as np

app = Flask(__name__)

# ==============================
# 🔴 MongoDB Connection
# ==============================

client = MongoClient("YOUR_MONGODB_CONNECTION_STRING")

db = client["YOUR_DATABASE_NAME"]
collection = db["intruder_logs"] // YOU CAN KEEP THE NAME BY UR CHOICE 

# ==============================
# 📁 Folder Setup
# ==============================

if not os.path.exists("face_data"):
    os.makedirs("face_data")

if not os.path.exists("static/images"):
    os.makedirs("static/images")

AUTHORIZED_FILE = "face_data/authorized.pkl"

# ==============================
# 📷 Capture Image
# ==============================

def capture_image():
    camera = cv2.VideoCapture(0)
    ret, frame = camera.read()

    if ret:
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"alert_{now}.jpg"
        filepath = os.path.join("static/images", filename)

        cv2.imwrite(filepath, frame)
        camera.release()
        return filename, filepath

    camera.release()
    return None, None

# ==============================
# 🧠 Register Authorized Face
# ==============================

@app.route("/register", methods=["GET"])
def register_face():

    image_filename, image_path = capture_image()

    if image_path is None:
        return "Camera Error"

    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces = face_cascade.detectMultiScale(gray, 1.2, 6)

    if len(faces) == 0:
        return "No Face Detected"

    (x, y, w, h) = faces[0]
    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (100, 100))
    face_vector = face.flatten()

    with open(AUTHORIZED_FILE, "wb") as f:
        pickle.dump(face_vector, f)

    return "Face Registered Successfully!"

# ==============================
# 🧠 Face Recognition
# ==============================

def recognize_face(image_path):

    if not os.path.exists(AUTHORIZED_FILE):
        return "NO REGISTERED FACE"

    with open(AUTHORIZED_FILE, "rb") as f:
        authorized_face = pickle.load(f)

    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces = face_cascade.detectMultiScale(gray, 1.2, 6)

    if len(faces) == 0:
        return "NO FACE"

    (x, y, w, h) = faces[0]
    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (100, 100))
    face_vector = face.flatten()

    similarity = np.linalg.norm(authorized_face - face_vector)
    print("Similarity Score:", similarity)

    if similarity < 20000:
        return "SAFE"
    else:
        return "INTRUDER"

# ==============================
# 📲 Telegram
# ==============================

BOT_TOKEN = "YOUR_TOKEN_ID"
CHAT_ID = "CHAT_ID"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def send_telegram_photo(image_filename):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    image_path = os.path.join("static/images", image_filename)

    with open(image_path, "rb") as photo:
        requests.post(url, data={"chat_id": CHAT_ID}, files={"photo": photo})

# ==============================
# 🚨 ALERT ROUTE (FINAL VERSION)
# ==============================

@app.route("/alert", methods=["POST"])
def alert():
    zone = request.json.get("zone", "Lab-Entrance")
    now = datetime.now()

    image_filename, image_path = capture_image()

    person_status = "NO FACE"
    if image_path:
        person_status = recognize_face(image_path)

    data = {
        "zone": zone,
        "event": person_status,
        "day": now.strftime("%A"),
        "date": now.strftime("%d-%m-%Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "image": image_filename,
        "timestamp": now
    }

    collection.insert_one(data)

    # Telegram message
    if person_status == "SAFE":
        message = f"✅ AUTHORIZED SAFE\nZone: {zone}"
    elif person_status == "INTRUDER":
        message = f"🚨 INTRUDER ALERT\nZone: {zone}"
    elif person_status == "NO FACE":
        message = f"⚠ NO FACE DETECTED\nZone: {zone}"
    else:
        message = f"ℹ {person_status}"

    send_telegram_message(message)

    if image_filename:
        send_telegram_photo(image_filename)

    return jsonify({"status": person_status}), 200

# ==============================
# 📊 Dashboard
# ==============================

@app.route("/")
def dashboard():
    alerts = list(collection.find({}, {"_id": 0}).sort("timestamp", -1))
    total = collection.count_documents({})
    return render_template("dashboard.html", alerts=alerts, total=total)

# ==============================
# ▶ Run Server
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
