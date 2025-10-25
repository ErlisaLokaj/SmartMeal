"""Recipe mongo models"""
from typing import List, Optional

class RecipeModel:
    def __init__(self, name: str, ingredients: List[str], steps: List[str], source: Optional[str] = None):
        self.name = name
        self.ingredients = ingredients
        self.steps = steps
        self.source = source

    def ingredient_count(self) -> int: return len(self.ingredients)
    def step_count(self) -> int: return len(self.steps)

    def to_dict(self) -> dict:
        return {"name": self.name, "ingredients": self.ingredients, "steps": self.steps, "source": self.source}
