"""
Database Schemas for Oil & Gas Drawing Intelligence MVP

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (handled by the Flames platform conventions).
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class Project(BaseModel):
    name: str = Field(..., description="Project display name")
    code: Optional[str] = Field(None, description="Project code or number")
    description: Optional[str] = Field(None, description="Short description")
    revision: Optional[str] = Field(None, description="Current revision tag")
    created_by: Optional[str] = Field(None, description="User who created the project")


class Upload(BaseModel):
    project_id: str = Field(..., description="Related project id (string)")
    filename: str = Field(..., description="Original file name")
    filepath: str = Field(..., description="Server-side path to stored file")
    filetype: str = Field(..., description="Detected type: pdf|dxf|dwg|step|ifc|obj|other")
    size_bytes: int = Field(..., description="File size in bytes")


class ExtractionItem(BaseModel):
    project_id: str = Field(..., description="Project id")
    upload_id: str = Field(..., description="Upload id")
    kind: str = Field(..., description="tag|bom|text|geometry|meta")
    label: str = Field(..., description="Display label, e.g., tag string or part name")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Additional attributes")
    page: Optional[int] = Field(None, description="Page index for 2D docs")
    confidence: Optional[float] = Field(None, description="0-1 confidence score if applicable")


class DocumentDraft(BaseModel):
    project_id: str = Field(..., description="Project id")
    doc_type: str = Field(..., description="tag-index|bom|summary")
    title: str = Field(..., description="Document title")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="List of rows/entries")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


# Example schemas kept for reference but not used by the MVP directly
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True


class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
