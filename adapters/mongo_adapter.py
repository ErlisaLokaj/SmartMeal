"""Mongo adapter for recipes"""
from pymongo import MongoClient
from core.config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["smartmeal"]
recipes_collection = db["recipes"]

def search_recipes_by_ingredient(ingredient: str):
    return list(recipes_collection.find(
        {"ingredients": {"$regex": ingredient, "$options": "i"}},
        {"_id": 0, "name": 1, "ingredients": 1, "steps": 1, "source": 1}
    ))

def search_recipes_by_name(name: str):
    return list(recipes_collection.find(
        {"name": {"$regex": name, "$options": "i"}},
        {"_id": 0, "name": 1, "ingredients": 1, "steps": 1, "source": 1}
    ))
