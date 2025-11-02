"""
Shopping list domain mappers.
Handles transformation between ORM models and DTOs for shopping-related entities.
"""

from domain.models import ShoppingList
from domain.schemas.shopping_schemas import (
    ShoppingListResponse,
    ShoppingListItemResponse,
)


class ShoppingMapper:
    """Mapper for shopping list transformations."""

    @staticmethod
    def to_response(shopping_list: ShoppingList) -> ShoppingListResponse:
        """
        Convert ORM ShoppingList to ShoppingListResponse DTO.

        Args:
            shopping_list: ShoppingList ORM instance with items loaded

        Returns:
            ShoppingListResponse DTO with all list data
        """
        items = [
            ShoppingListItemResponse(
                list_item_id=item.list_item_id,
                list_id=item.list_id,
                ingredient_id=item.ingredient_id,
                ingredient_name=item.ingredient_name,
                needed_qty=float(item.needed_qty),
                unit=item.unit,
                checked=item.checked,
                from_recipe_id=item.from_recipe_id,
                note=item.note,
            )
            for item in shopping_list.items
        ]

        return ShoppingListResponse(
            list_id=shopping_list.list_id,
            user_id=shopping_list.user_id,
            plan_id=shopping_list.plan_id,
            created_at=shopping_list.created_at,
            status=shopping_list.status,
            items=items,
        )
