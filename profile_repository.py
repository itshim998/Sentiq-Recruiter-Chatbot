"""
profile_repository.py
---------------------
ResumeIQ — Profile Persistence Repository

Responsibility:
- Abstract MongoDB operations for user profiles
- Provide clean CRUD methods
- Hide database details from business logic

NO AI logic
NO parsing
NO generation
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import os

from bson import ObjectId
from dotenv import load_dotenv

# ------------------------------
# Environment & DB setup (shared single client)
# ------------------------------

load_dotenv()

from db import db

profiles_collection = db["profiles"]

# ------------------------------
# Helpers
# ------------------------------

def _serialize_profile(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MongoDB document to JSON-safe dict.
    """
    if not doc:
        return doc

    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    
    # Convert datetime objects to ISO format strings
    if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
        doc["created_at"] = doc["created_at"].isoformat()
    if "updated_at" in doc and hasattr(doc["updated_at"], "isoformat"):
        doc["updated_at"] = doc["updated_at"].isoformat()
    
    return doc


# ------------------------------
# Create
# ------------------------------

def create_profile(profile_document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Insert a new structured profile document.

    Args:
        profile_document: Structured profile dict

    Returns:
        Inserted profile document (with _id)
    """

    now = datetime.utcnow()
    profile_document.setdefault("created_at", now)
    profile_document.setdefault("updated_at", now)

    result = profiles_collection.insert_one(profile_document)
    profile_document["_id"] = str(result.inserted_id)
    return profile_document


# ------------------------------
# Read
# ------------------------------

def get_profile_by_id(profile_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a profile by its ID.
    """

    try:
        oid = ObjectId(profile_id)
    except Exception:
        return None

    doc = profiles_collection.find_one({"_id": oid})
    return _serialize_profile(doc)


def list_profiles(limit: int = 20) -> List[Dict[str, Any]]:
    """
    List recent profiles.
    """

    cursor = (
        profiles_collection
        .find({})
        .sort("created_at", -1)
        .limit(limit)
    )

    return [_serialize_profile(doc) for doc in cursor]


# ------------------------------
# Update
# ------------------------------

def update_profile(
    profile_id: str,
    updates: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Update fields in an existing profile.

    Args:
        profile_id: Profile ObjectId as string
        updates: Dict of fields to update

    Returns:
        Updated profile or None if not found
    """

    try:
        oid = ObjectId(profile_id)
    except Exception:
        return None

    updates["updated_at"] = datetime.utcnow()

    result = profiles_collection.find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=True
    )

    return _serialize_profile(result)


# ------------------------------
# Delete (optional, soft-safe)
# ------------------------------

def delete_profile(profile_id: str) -> bool:
    """
    Permanently delete a profile.
    Use sparingly; prefer logical deletion if needed later.
    """

    try:
        oid = ObjectId(profile_id)
    except Exception:
        return False

    result = profiles_collection.delete_one({"_id": oid})
    return result.deleted_count == 1


# ------------------------------
# Optional local test
# ------------------------------

if __name__ == "__main__":
    sample_profile = {
        "source": "manual",
        "raw_text": "Sample text",
        "structured": {
            "personal": {"name": "Test User"},
            "skills": [],
            "education": [],
            "projects": [],
            "experience": [],
            "certifications": [],
            "links": {}
        }
    }

    created = create_profile(sample_profile)
    print("Created:", created)

    fetched = get_profile_by_id(created["_id"])
    print("Fetched:", fetched)

    updated = update_profile(created["_id"], {"source": "updated"})
    print("Updated:", updated)

    all_profiles = list_profiles()
    print("Profiles:", all_profiles)
