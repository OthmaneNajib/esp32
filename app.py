import os
from datetime import datetime, timezone

import certifi
from flask import Flask, request, jsonify
from pymongo import MongoClient, DESCENDING

API_KEY = os.environ.get("API_KEY", "change-moi")
MONGO_URI = os.environ["MONGO_URI"]  # obligatoire

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=5000,
)
col = client["iot"]["temperatures"]

# Index pour trier par date
col.create_index([("ts", DESCENDING)])
# Suppression automatique après 30 jours (le plan gratuit est limité à 512 Mo)
col.create_index("ts", name="ttl_30j", expireAfterSeconds=30 * 24 * 3600)

app = Flask(__name__)


@app.post("/api/mesures")
def ajouter():
    if request.headers.get("X-API-Key") != API_KEY:
        return jsonify(erreur="non autorise"), 401

    data = request.get_json(silent=True) or {}
    try:
        temp = float(data["temperature"])
    except (KeyError, ValueError, TypeError):
        return jsonify(erreur="temperature invalide"), 400

    if not -40 <= temp <= 150:
        return jsonify(erreur="valeur hors plage"), 400

    col.insert_one({
        "device": str(data.get("device", "esp32-01"))[:32],
        "temperature": round(temp, 2),
        "ts": datetime.now(timezone.utc),
    })
    return jsonify(ok=True), 201


@app.get("/api/mesures")
def lister():
    try:
        limite = min(int(request.args.get("limit", 100)), 1000)
    except ValueError:
        limite = 100

    docs = col.find({}, {"_id": 0}).sort("ts", DESCENDING).limit(limite)
    return jsonify([{**d, "ts": d["ts"].isoformat()} for d in docs])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)