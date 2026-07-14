from __future__ import annotations

from pydantic import BaseModel, Field


class GroceryItem(BaseModel):
    name: str = Field(description="Plain grocery ingredient or household item name")
    quantity: float = Field(default=1, ge=0, description="Numeric amount requested")
    unit: str = Field(default="item", description="Unit such as item, lb, oz, can, bunch, gallon")
    notes: str = Field(default="", description="Brand, dietary, size, ripeness, or other qualifiers")


class GroceryList(BaseModel):
    items: list[GroceryItem]
