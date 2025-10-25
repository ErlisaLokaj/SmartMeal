"""Schemes for API"""
from pydantic import BaseModel
from typing import List, Optional, Dict

class Recipe(BaseModel):
    name: str
    ingredients: List[str]
    steps: List[str]
    source: Optional[str] = None

class Pagination(BaseModel):
    page: int
    size: int
    total: int
    pages: int

class RecipeSearchResponse(BaseModel):
    data: List[Recipe]
    meta: Pagination

class Plan(BaseModel):
    user: str
    goal: str
    ingredient: str
    recipes: List[Recipe]
    substitutes: List[str] = []
    pantry: List[str] = []
    shopping_list: Dict[str, List[str]] = {}
