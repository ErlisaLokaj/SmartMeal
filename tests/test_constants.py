"""
Realistic test constants for SmartMeal test suite.

This module contains realistic values based on real-world food quantities,
nutrition data, and user profiles to make tests more meaningful and maintainable.
"""

from decimal import Decimal
from datetime import date, timedelta

# =============================================================================
# USER PROFILES - Realistic personas with diverse backgrounds
# =============================================================================

REALISTIC_USERS = {
    "sarah": {
        "full_name": "Sarah Martinez",
        "email_prefix": "sarah.martinez",
        "dietary_goal": "weight_loss",
        "activity": "moderate",
        "kcal_target": 1800,
        "protein_target_g": 120.0,
        "carb_target_g": 180.0,
        "fat_target_g": 60.0,
    },
    "michael": {
        "full_name": "Michael Chen",
        "email_prefix": "michael.chen",
        "dietary_goal": "muscle_gain",
        "activity": "very_active",
        "kcal_target": 2800,
        "protein_target_g": 180.0,
        "carb_target_g": 350.0,
        "fat_target_g": 80.0,
    },
    "emma": {
        "full_name": "Emma Johnson",
        "email_prefix": "emma.johnson",
        "dietary_goal": "maintenance",
        "activity": "light",
        "kcal_target": 2000,
        "protein_target_g": 100.0,
        "carb_target_g": 250.0,
        "fat_target_g": 65.0,
    },
    "raj": {
        "full_name": "Raj Patel",
        "email_prefix": "raj.patel",
        "dietary_goal": "health",
        "activity": "moderate",
        "kcal_target": 2200,
        "protein_target_g": 110.0,
        "carb_target_g": 275.0,
        "fat_target_g": 70.0,
    },
}

# =============================================================================
# INGREDIENT QUANTITIES - Based on typical household amounts
# =============================================================================

# Grains & Starches (typical pantry stock)
GRAINS = {
    "rice": {"quantity": Decimal("2000"), "unit": "g"},  # 2kg bag
    "pasta": {"quantity": Decimal("500"), "unit": "g"},  # Standard box
    "flour": {"quantity": Decimal("1000"), "unit": "g"},  # 1kg bag
    "oats": {"quantity": Decimal("500"), "unit": "g"},  # Breakfast supply
    "quinoa": {"quantity": Decimal("400"), "unit": "g"},  # Specialty grain
}

# Vegetables (fresh produce quantities)
VEGETABLES = {
    "tomato": {"quantity": Decimal("400"), "unit": "g"},  # ~4 medium tomatoes
    "onion": {"quantity": Decimal("300"), "unit": "g"},  # ~2 medium onions
    "carrot": {"quantity": Decimal("500"), "unit": "g"},  # ~5 medium carrots
    "potato": {"quantity": Decimal("1000"), "unit": "g"},  # ~6-7 medium potatoes
    "bell pepper": {"quantity": Decimal("200"), "unit": "g"},  # 1 large pepper
    "lettuce": {"quantity": Decimal("250"), "unit": "g"},  # 1 head
    "cucumber": {"quantity": Decimal("300"), "unit": "g"},  # 1 large cucumber
    "broccoli": {"quantity": Decimal("350"), "unit": "g"},  # 1 head
}

# Proteins (typical purchase amounts)
PROTEINS = {
    "chicken breast": {"quantity": Decimal("800"), "unit": "g"},  # Family pack
    "ground beef": {"quantity": Decimal("500"), "unit": "g"},  # Standard pack
    "salmon": {"quantity": Decimal("400"), "unit": "g"},  # 2 fillets
    "tofu": {"quantity": Decimal("400"), "unit": "g"},  # Standard block
    "eggs": {"quantity": Decimal("12"), "unit": "pieces"},  # 1 dozen
    "greek yogurt": {"quantity": Decimal("500"), "unit": "g"},  # Large container
}

# Dairy & Alternatives
DAIRY = {
    "milk": {"quantity": Decimal("1000"), "unit": "ml"},  # 1 liter
    "cheese": {"quantity": Decimal("200"), "unit": "g"},  # Block of cheese
    "butter": {"quantity": Decimal("250"), "unit": "g"},  # 1 stick
    "cream": {"quantity": Decimal("200"), "unit": "ml"},  # Small carton
}

# Spices & Condiments (long-lasting pantry items)
SPICES = {
    "salt": {"quantity": Decimal("500"), "unit": "g"},  # Standard container
    "pepper": {"quantity": Decimal("50"), "unit": "g"},  # Pepper shaker
    "olive oil": {"quantity": Decimal("500"), "unit": "ml"},  # Small bottle
    "soy sauce": {"quantity": Decimal("250"), "unit": "ml"},  # Standard bottle
    "garlic": {"quantity": Decimal("100"), "unit": "g"},  # ~1 bulb
    "ginger": {"quantity": Decimal("80"), "unit": "g"},  # Fresh root
}

# Fruits
FRUITS = {
    "apple": {"quantity": Decimal("600"), "unit": "g"},  # ~4 medium apples
    "banana": {"quantity": Decimal("500"), "unit": "g"},  # ~4 bananas
    "orange": {"quantity": Decimal("700"), "unit": "g"},  # ~4 oranges
    "strawberry": {"quantity": Decimal("250"), "unit": "g"},  # 1 container
}

# =============================================================================
# WASTE QUANTITIES - Realistic food waste amounts
# =============================================================================

# Common waste scenarios (typically smaller than purchase amounts)
WASTE_AMOUNTS = {
    "expired_vegetables": Decimal("150"),  # Portion of produce that spoiled
    "leftover_rice": Decimal("200"),  # Cooked rice not eaten
    "moldy_bread": Decimal("300"),  # Half a loaf
    "spoiled_milk": Decimal("500"),  # Half-full container
    "freezer_burn_meat": Decimal("250"),  # Small portion of meat
    "wilted_lettuce": Decimal("100"),  # Portion of salad greens
}

# =============================================================================
# RECIPE NUTRITION - Realistic per-serving values
# =============================================================================

RECIPE_NUTRITION = {
    "light_meal": {  # Salad, soup
        "calories": 350,
        "protein_g": 15.0,
        "carbs_g": 45.0,
        "fat_g": 12.0,
    },
    "moderate_meal": {  # Chicken with rice
        "calories": 550,
        "protein_g": 35.0,
        "carbs_g": 60.0,
        "fat_g": 18.0,
    },
    "heavy_meal": {  # Pasta with meat sauce
        "calories": 750,
        "protein_g": 40.0,
        "carbs_g": 85.0,
        "fat_g": 28.0,
    },
    "snack": {  # Yogurt with fruit
        "calories": 180,
        "protein_g": 8.0,
        "carbs_g": 28.0,
        "fat_g": 4.0,
    },
}

# =============================================================================
# EXPIRATION DATES - Realistic shelf life
# =============================================================================


def get_expiration_date(food_type: str) -> date:
    """
    Get realistic expiration date based on food type.

    Args:
        food_type: Type of food (fresh_produce, dairy, meat, pantry, frozen)

    Returns:
        Realistic expiration date from today
    """
    today = date.today()

    shelf_life = {
        "fresh_produce": 5,  # 5 days
        "leafy_greens": 3,  # 3 days
        "dairy": 7,  # 1 week
        "meat_fresh": 2,  # 2 days
        "meat_frozen": 90,  # 3 months
        "pantry_dry": 180,  # 6 months
        "pantry_opened": 30,  # 1 month
        "bread": 4,  # 4 days
        "eggs": 21,  # 3 weeks
    }

    days = shelf_life.get(food_type, 7)  # Default 1 week
    return today + timedelta(days=days)


# =============================================================================
# CUISINE PREFERENCES - Realistic cuisine types
# =============================================================================

CUISINES = {
    "popular": ["italian", "asian", "mexican", "american"],
    "healthy": ["mediterranean", "japanese", "middle_eastern"],
    "comfort": ["american", "british", "southern"],
    "spicy": ["indian", "thai", "mexican", "korean"],
}

# =============================================================================
# DIETARY TAGS - Common dietary preferences
# =============================================================================

DIETARY_TAGS = {
    "restrictions": ["vegetarian", "vegan", "gluten_free", "dairy_free", "nut_free"],
    "goals": ["high_protein", "low_carb", "low_fat", "keto", "paleo"],
    "lifestyle": ["quick", "easy", "meal_prep", "budget_friendly"],
    "occasions": ["breakfast", "lunch", "dinner", "snack", "dessert"],
}

# =============================================================================
# COMMON ALLERGIES - Top 9 allergens
# =============================================================================

COMMON_ALLERGENS = [
    "peanut",
    "tree nut",  # almonds, walnuts, cashews, etc.
    "milk",
    "egg",
    "wheat",
    "soy",
    "fish",
    "shellfish",
    "sesame",
]
