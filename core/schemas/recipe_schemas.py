"""Pydantic schemas for MongoDB recipe documents."""

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime


class RecipeIngredient(BaseModel):
    """Embedded ingredient in a recipe."""
    ingredient_id: UUID = Field(default_factory=uuid4)
    name: str
    quantity: float
    unit: str
    optional: bool = False
    prep_note: str = ""


class RecipeStep(BaseModel):
    """Embedded step in a recipe."""
    order: int
    text: str
    duration_min: int


class RecipeImage(BaseModel):
    """Embedded image in a recipe."""
    image_id: UUID = Field(default_factory=uuid4)
    url: str
    caption: str = ""


class RecipeYields(BaseModel):
    """Recipe yield information."""
    servings: int
    serving_unit: str = "servings"


class NutritionPerServing(BaseModel):
    """Nutrition information per serving."""
    kcal: int = 0
    protein_g: float = 0
    carb_g: float = 0
    fat_g: float = 0


class RecipeNutrition(BaseModel):
    """Nutrition wrapper."""
    per_serving: NutritionPerServing


class Recipe(BaseModel):
    """Complete recipe document for MongoDB."""
    id: UUID = Field(default_factory=uuid4, alias="_id")
    title: str
    slug: str = ""  # Auto-generated from title if empty
    cuisine_id: UUID = Field(default_factory=uuid4)
    tags: List[str] = []
    yields_: RecipeYields = Field(alias="yields")
    ingredients: List[RecipeIngredient]
    steps: List[RecipeStep]
    nutrition: RecipeNutrition
    images: List[RecipeImage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_deleted: bool = False

    class Config:
        populate_by_name = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat() + "Z"
        }

    def model_post_init(self, __context):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = self.title.lower().replace(" ", "-").replace("'", "")


# Simplified creation models for easier recipe building
class SimpleIngredient(BaseModel):
    """Simplified ingredient input."""
    name: str
    quantity: float
    unit: str
    optional: bool = False
    prep_note: str = ""


class SimpleStep(BaseModel):
    """Simplified step input."""
    text: str
    duration_min: int = 5


class RecipeCreate(BaseModel):
    """Simplified recipe creation."""
    title: str
    cuisine: str = "International"
    tags: List[str] = []
    servings: int = 4
    ingredients: List[SimpleIngredient]
    steps: List[SimpleStep]
    kcal: int = 0
    protein_g: float = 0
    carb_g: float = 0
    fat_g: float = 0

    def to_recipe(self) -> Recipe:
        """Convert to full Recipe model."""
        # Convert ingredients
        recipe_ingredients = [
            RecipeIngredient(
                name=ing.name,
                quantity=ing.quantity,
                unit=ing.unit,
                optional=ing.optional,
                prep_note=ing.prep_note
            )
            for ing in self.ingredients
        ]

        # Convert steps with auto-numbering
        recipe_steps = [
            RecipeStep(order=idx, text=step.text, duration_min=step.duration_min)
            for idx, step in enumerate(self.steps, start=1)
        ]

        # Build full recipe
        return Recipe(
            title=self.title,
            tags=self.tags,
            yields=RecipeYields(servings=self.servings),
            ingredients=recipe_ingredients,
            steps=recipe_steps,
            nutrition=RecipeNutrition(
                per_serving=NutritionPerServing(
                    kcal=self.kcal,
                    protein_g=self.protein_g,
                    carb_g=self.carb_g,
                    fat_g=self.fat_g
                )
            )
        )