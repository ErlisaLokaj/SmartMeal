from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class AllergyCreate(BaseModel):
    ingredient_id: UUID
    note: Optional[str] = None


class AllergyResponse(BaseModel):
    ingredient_id: UUID
    note: Optional[str] = None
    
    class Config:
        from_attributes = True


class PreferenceCreate(BaseModel):
    tag: str = Field(..., min_length=1, max_length=100)
    strength: PreferenceStrength
    
    @validator('tag')
    def normalize_tag(cls, v):
        return v.lower().strip()


class PreferenceResponse(BaseModel):
    tag: str
    strength: PreferenceStrength
    
    class Config:
        from_attributes = True


class DietaryProfileCreate(BaseModel):
    goal: GoalType
    activity: ActivityLevel
    kcal_target: Optional[int] = Field(None, ge=800, le=5000)
    protein_target_g: Optional[float] = Field(None, ge=0, le=500)
    carb_target_g: Optional[float] = Field(None, ge=0, le=1000)
    fat_target_g: Optional[float] = Field(None, ge=0, le=300)
    cuisine_likes: Optional[List[str]] = []
    cuisine_dislikes: Optional[List[str]] = []


class DietaryProfileResponse(BaseModel):
    goal: GoalType
    activity: ActivityLevel
    kcal_target: Optional[int]
    protein_target_g: Optional[float]
    carb_target_g: Optional[float]
    fat_target_g: Optional[float]
    cuisine_likes: List[str]
    cuisine_dislikes: List[str]
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ProfileUpdateRequest(BaseModel):
    """Complete profile update request"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    dietary_profile: Optional[DietaryProfileCreate] = None
    allergies: Optional[List[AllergyCreate]] = []
    preferences: Optional[List[PreferenceCreate]] = []


class UserProfileResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    dietary_profile: Optional[DietaryProfileResponse]
    allergies: List[AllergyResponse]
    preferences: List[PreferenceResponse]
    
    class Config:
        from_attributes = True