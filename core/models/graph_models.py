"""Ingredient graph models"""

class IngredientNode:
    def __init__(self, name: str, substitutes: list[str] | None = None):
        self.name = name
        self.substitutes = substitutes or []

    def to_dict(self) -> dict:
        return {"ingredient": self.name, "substitutes": self.substitutes}
