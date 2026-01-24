"""
profile_structurer.py
---------------------
ResumeIQ — Profile Structuring & Persistence Layer

Responsibility:
- Convert raw profile text into structured JSON using LLM
- Enforce schema correctness
- Store structured profile in MongoDB

Uses:
- SentIQ LLM Gateway (Gemini + Groq)
- MongoDB (primary persistence)

This is the FIRST MongoDB-touching intelligence module.
"""

from datetime import datetime
import json
import os
from typing import Dict, Any

from dotenv import load_dotenv

from llm_adapter import call_llm_router

# ------------------------------
# Environment & DB setup (shared single client)
# ------------------------------

load_dotenv()

from db import db

profiles_collection = db["profiles"]

# ------------------------------
# LLM Prompt Template
# ------------------------------

PROFILE_STRUCTURING_PROMPT = """
You are an expert resume analyst and information structuring engine.

Your task:
Convert the following unstructured profile text into a clean, structured JSON object.

Rules (STRICT):
- Output VALID JSON ONLY
- Do NOT include explanations or markdown
- If a section is missing, return an empty list []
- Be concise but accurate
- Do NOT invent information

Required JSON schema:
{
  "personal": {
    "name": "",
    "email": "",
    "phone": "",
    "location": ""
  },
  "education": [
    {
      "degree": "",
      "institution": "",
      "year": ""
    }
  ],
  "skills": [
    {
      "category": "",
      "items": []
    }
  ],
  "projects": [
    {
      "title": "",
      "description": "",
      "technologies": []
    }
  ],
  "experience": [
    {
      "role": "",
      "organization": "",
      "duration": "",
      "details": ""
    }
  ],
  "certifications": [],
  "links": {
    "github": "",
    "linkedin": "",
    "portfolio": ""
  }
}

Profile Text:
----------------
{profile_text}
----------------
"""

# ------------------------------
# Public API
# ------------------------------

def structure_and_store_profile(
    profile_text: str,
    source: str = "manual"
) -> Dict[str, Any]:
    """
    Converts profile text into structured JSON using LLM
    and stores it in MongoDB.

    Args:
        profile_text: Cleaned profile text (from profile_parser)
        source: manual | pdf | txt | linkedin

    Returns:
        Stored profile document (dict)

    Raises:
        ValueError if structuring fails
    """

    if not profile_text or not isinstance(profile_text, str):
        raise ValueError("Invalid profile text")

    prompt = PROFILE_STRUCTURING_PROMPT.replace("{profile_text}", profile_text)


    raw_response = call_llm_router(
        prompt=prompt,
        task="profile_structuring",
        use_simulation=False
    )

    try:
        structured_profile = json.loads(raw_response)
    except Exception as e:
        raise ValueError(f"LLM returned invalid JSON: {e}")

    # Basic sanity check
    if not isinstance(structured_profile, dict):
        raise ValueError("Structured profile is not a JSON object")

    # Attach system metadata
    profile_document = {
        "source": source,
        "raw_text": profile_text,
        "structured": structured_profile,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = profiles_collection.insert_one(profile_document)
    profile_document["_id"] = str(result.inserted_id)
    
    # Convert datetime to ISO string for JSON serialization
    profile_document["created_at"] = profile_document["created_at"].isoformat()
    profile_document["updated_at"] = profile_document["updated_at"].isoformat()

    return profile_document

# ------------------------------
# Optional local test
# ------------------------------

if __name__ == "__main__":
    sample_profile = """
    Sounak Das
    B.Tech CSE (AI & ML), RCC Institute of Information Technology

    Skills: Python, Machine Learning, Flask, MongoDB
    Projects: AI Resume Builder, RecruiterIQ
    GitHub: https://github.com/example
    """

    stored = structure_and_store_profile(sample_profile, source="manual")
    print("Stored profile ID:", stored["_id"])
