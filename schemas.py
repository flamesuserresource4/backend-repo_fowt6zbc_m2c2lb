"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional

# Example schemas (replace with your own):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Helmet order schema and DTOs
class Order(BaseModel):
    """
    Helmet orders collection schema
    Collection name: "order"
    """
    customer_name: str = Field(..., min_length=2, description="Customer full name")
    email: Optional[EmailStr] = Field(None, description="Customer email for receipt")
    phone: str = Field(..., min_length=6, description="WhatsApp or phone number")
    address: str = Field(..., min_length=5, description="Shipping address")
    model: str = Field(..., description="Helmet model name")
    size: str = Field(..., description="Helmet size")
    quantity: int = Field(1, ge=1, le=20, description="Quantity ordered")
    notes: Optional[str] = Field(None, description="Additional notes")

class OrderResponse(BaseModel):
    id: str
    status: str
    sheet_status: str
    notification_status: str
