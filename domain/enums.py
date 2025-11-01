"""
Domain enums for SmartMeal application.
Contains all enumeration types used across the domain models.
"""

import enum


class GoalType(str, enum.Enum):
    """Dietary goal types"""

    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    HEALTH = "health"


class ActivityLevel(str, enum.Enum):
    """Physical activity levels"""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class PreferenceStrength(str, enum.Enum):
    """User preference intensity"""

    AVOID = "avoid"
    NEUTRAL = "neutral"
    LIKE = "like"
    LOVE = "love"
