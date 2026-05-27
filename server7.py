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

client = MongoClient(
    "mongodb+srv://ganeshchettipally:Ganesh0505@cluster0.zpjpsun.mongodb.net/?retryWrites=true&w=majority"
)

db = client["iot_database"]
collection = db["intruder_logs"]

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

@app.route("/register/<name>", methods=["GET"])
def register_face(name):

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

    # Load existing faces
    if os.path.exists(AUTHORIZED_FILE):
        with open(AUTHORIZED_FILE, "rb") as f:
            authorized_faces = pickle.load(f)
    else:
        authorized_faces = {}

    authorized_faces[name] = face_vector

    with open(AUTHORIZED_FILE, "wb") as f:
        pickle.dump(authorized_faces, f)

    return f"{name} Registered Successfully!"

# ==============================
# 🧠 Face Recognition
# ==============================

def recognize_face(image_path):

    if not os.path.exists(AUTHORIZED_FILE):
        return None, "NO REGISTERED FACE"

    with open(AUTHORIZED_FILE, "rb") as f:
        authorized_faces = pickle.load(f)

    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    faces = face_cascade.detectMultiScale(gray, 1.2, 6)

    if len(faces) == 0:
        return None, "NO FACE"

    (x, y, w, h) = faces[0]
    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (100, 100))
    face_vector = face.flatten()

    best_match = None
    lowest_distance = float("inf")

    for name, stored_vector in authorized_faces.items():
        distance = np.linalg.norm(stored_vector - face_vector)

        if distance < lowest_distance:
            lowest_distance = distance
            best_match = name

    print("Best Match:", best_match)
    print("Distance:", lowest_distance)

    if lowest_distance < 20000:
        return best_match, "SAFE"
    else:
        return None, "INTRUDER"

# ==============================
# 📲 Telegram
# ==============================

BOT_TOKEN = "8572205880:YOUR_NEW_TOKEN"
CHAT_ID = "6365701002"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def send_telegram_photo(image_filename):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    image_path = os.path.join("static/images", image_filename)

    with open(image_path, "rb") as photo:
        requests.post(url, data={"chat_id": CHAT_ID}, files={"photo": photo})

# ==============================
# 🚨 ALERT ROUTE (UPDATED)
# ==============================

@app.route("/alert", methods=["POST"])
def alert():
    zone = request.json.get("zone", "Lab-Entrance")
    now = datetime.now()

    image_filename, image_path = capture_image()

    name = None
    status = "NO FACE"

    if image_path:
        name, status = recognize_face(image_path)

    # For Dashboard & MongoDB
    if status == "SAFE":
        event_text = f"SAFE ({name})"
    else:
        event_text = status

    data = {
        "zone": zone,
        "event": event_text,
        "day": now.strftime("%A"),
        "date": now.strftime("%d-%m-%Y"),
        "time": now.strftime("%I:%M:%S %p"),
        "image": image_filename,
        "timestamp": now
    }

    collection.insert_one(data)

    # Telegram Message
    if status == "SAFE":
        message = f"✅ AUTHORIZED SAFE ({name})\nZone: {zone}"
    elif status == "INTRUDER":
        message = f"🚨 INTRUDER ALERT\nZone: {zone}"
    else:
        message = f"⚠ {status}\nZone: {zone}"

    send_telegram_message(message)

    if image_filename:
        send_telegram_photo(image_filename)

    # 🔥 THIS IS IMPORTANT FOR ESP
    if status == "SAFE":
        return jsonify({"status": "SAFE", "name": name}), 200
    elif status == "INTRUDER":
        return jsonify({"status": "INTRUDER"}), 200
    else:
        return jsonify({"status": status}), 200

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
    app.run(host="0.0.0.0", port=8000)
