"""
portfolio_repository.py
-----------------------
ResumeIQ — Portfolio Repository

Responsibility:
- MongoDB operations for portfolios
- Provide clean retrieval methods
"""

from typing import Optional, Dict, Any
from bson import ObjectId
from datetime import datetime

from db import db

portfolios_collection = db["portfolios"]


def _serialize_portfolio(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert MongoDB document to JSON-safe dict.
    """
    if not doc:
        return None

    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    
    if "profile_id" in doc and isinstance(doc["profile_id"], ObjectId):
        doc["profile_id"] = str(doc["profile_id"])
    
    if "resume_id" in doc and isinstance(doc["resume_id"], ObjectId):
        doc["resume_id"] = str(doc["resume_id"])
    
    # Convert datetime objects to ISO format strings
    if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
        doc["created_at"] = doc["created_at"].isoformat()
    
    return doc


def get_portfolio_by_id(portfolio_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a portfolio document by ID.

    Args:
        portfolio_id (str): Portfolio MongoDB ObjectId as string

    Returns:
        dict | None
    """
    try:
        doc = portfolios_collection.find_one({"_id": ObjectId(portfolio_id)})
        return _serialize_portfolio(doc)
    except Exception:
        return None


def get_portfolio_by_resume_id(resume_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the most recent portfolio for a given resume.

    Args:
        resume_id (str): Resume MongoDB ObjectId as string

    Returns:
        dict | None
    """
    try:
        doc = portfolios_collection.find_one(
            {"resume_id": ObjectId(resume_id)},
            sort=[("created_at", -1)]
        )
        return _serialize_portfolio(doc)
    except Exception:
        return None
