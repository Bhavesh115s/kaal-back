import json, os, requests
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

JINA_API_KEY = os.getenv("JINA_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT_DIR, "data", "all_verses_with_themes.json")

def get_embedding(text):
    headers = {"Authorization": f"Bearer {JINA_API_KEY}"}
    payload = {
        "model": "jina-embeddings-v3",
        "task": "retrieval.passage",
        "dimensions": 1024,
        "input": [text]
    }
    res = requests.post("https://api.jina.ai/v1/embeddings", json=payload, headers=headers)
    return res.json()["data"][0]["embedding"]

def pinecone_metadata_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, list):
        return [str(item) for item in value]

    return json.dumps(value, ensure_ascii=False)

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    shlokas = json.load(f)

for i, verse in enumerate(shlokas):

    # 🔥 Use optimized embedding text
    text = verse["embedding_text"]

    vector = get_embedding(text)

    index.upsert([
        {
            "id": verse["id"],   # better than shloka-i
            "values": vector,
            "metadata": {
                "chapter": pinecone_metadata_value(verse["chapter"]),
                "verse": pinecone_metadata_value(verse["verse"]),
                "sanskrit": pinecone_metadata_value(verse["sanskrit"]),
                "meaning_english": pinecone_metadata_value(verse["meanings"].get("english")),
                "meaning_hindi": pinecone_metadata_value(verse["meanings"].get("hindi")),
                "meaning_hinglish": pinecone_metadata_value(verse["meanings"].get("hinglish")),
                "meaning_marathi": pinecone_metadata_value(verse["meanings"].get("marathi")),
                "core_meaning": pinecone_metadata_value(verse["core_meaning"]),
                "use_cases": pinecone_metadata_value(verse["use_cases"]),
                "priority": pinecone_metadata_value(verse["priority_score"]),
                "emotion_map": pinecone_metadata_value(verse["emotion_map"])
            }
        }
    ])

print("✅ Pinecone Shlokas Indexed Successfully")

