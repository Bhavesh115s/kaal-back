# scripts/seed_db.py
import json
from mongodb import events_collection, meditation_collection

with open("data/events.json") as f:
    events_collection.insert_many(json.load(f))

with open("data/meditation.json") as f:
    meditation_collection.insert_many(json.load(f))

