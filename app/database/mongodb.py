from pymongo import MongoClient
from app.config import settings

_client = None

def get_mongo_client() -> MongoClient:
    """
    Returns a singleton MongoClient instance.
    """
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI)
    return _client

def get_generations_collection():
    """
    Returns the generations collection.
    """
    client = get_mongo_client()
    db = client[settings.MONGODB_DB_NAME]
    return db["generations"]
