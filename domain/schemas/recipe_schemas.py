"""Pydantic schemas for MongoDB recipe documents."""

from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List, Optional, Dict, Any
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

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

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

    @field_serializer("id", "cuisine_id")
    def serialize_uuid(self, value: UUID) -> str:
        """Serialize UUID fields to strings."""
        return str(value)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime fields to ISO format."""
        return value.isoformat() + "Z"

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
                prep_note=ing.prep_note,
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
                    fat_g=self.fat_g,
                )
            ),
        )


# Add these to the existing recipe_schemas.py file


class RecipeRecommendation(BaseModel):
    """Recipe recommendation response."""

    model_config = ConfigDict(populate_by_name=True)

    recipe_id: str = Field(alias="_id")
    title: str
    slug: str
    tags: List[str]
    servings: int
    cuisine: str = Field(default="International", alias="cuisine_id")
    ingredients_count: int
    total_time_min: int = 0
    match_score: float = 0.0  # How well it matches user preferences
    pantry_match_count: int = 0  # How many pantry items it uses

    @classmethod
    def from_recipe(
        cls, recipe: Dict[str, Any], score: float = 0, pantry_matches: int = 0
    ):
        """Create from MongoDB recipe document."""
        # Calculate total time from steps
        total_time = sum(
            step.get("duration_min", 0) for step in recipe.get("steps", [])
        )

        return cls(
            _id=recipe.get("_id"),
            title=recipe.get("title", "Untitled"),
            slug=recipe.get("slug", ""),
            tags=recipe.get("tags", []),
            servings=recipe.get("yields", {}).get("servings", 4),
            cuisine_id=recipe.get("cuisine_id", "International"),
            ingredients_count=len(recipe.get("ingredients", [])),
            total_time_min=total_time,
            match_score=score,
            pantry_match_count=pantry_matches,
        )


class RecommendationRequest(BaseModel):
    """Request for recipe recommendations."""

    user_id: UUID
    limit: int = Field(default=10, ge=1, le=50)
    tags: Optional[List[str]] = None  # Optional tag filters
