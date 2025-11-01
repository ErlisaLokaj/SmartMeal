"""
Base repository interface for data access layer.
This follows the Repository pattern to separate business logic from data access.
"""

from typing import Generic, TypeVar, Optional, List, Type
from uuid import UUID
from sqlalchemy.orm import Session
from abc import ABC

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType], ABC):
    """
    Base repository providing common CRUD operations.
    All repositories should inherit from this class.
    """

    def __init__(self, db: Session, model: Type[ModelType]):
        self.db = db
        self.model = model

    def get_by_id(self, entity_id: UUID) -> Optional[ModelType]:
        """Get entity by ID"""
        return (
            self.db.query(self.model)
            .filter(
                self.model.user_id == entity_id
                if hasattr(self.model, "user_id")
                else getattr(self.model, f"{self.model.__tablename__}_id") == entity_id
            )
            .first()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all entities with pagination"""
        return self.db.query(self.model).offset(skip).limit(limit).all()

    def create(self, entity: ModelType) -> ModelType:
        """Create new entity"""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelType) -> ModelType:
        """Update existing entity"""
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity_id: UUID) -> bool:
        """Delete entity by ID"""
        entity = self.get_by_id(entity_id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def exists(self, entity_id: UUID) -> bool:
        """Check if entity exists"""
        return self.get_by_id(entity_id) is not None
