"""
resume_generator.py
-------------------
Generates ATS-optimized resumes from stored profiles.

Responsibilities:
- Fetch structured profile
- Call LLM to generate resume JSON
- Store resume in MongoDB
- Return JSON-serializable response
"""

import json
import os
import logging
from datetime import datetime


from bson import ObjectId
from dotenv import load_dotenv

from llm_adapter import call_llm_router
from profile_repository import get_profile_by_id
from resume_schema import validate_resume_schema

logger = logging.getLogger(__name__)

# -------------------------
# Environment & DB setup
# -------------------------

load_dotenv()
from db import db
resumes_collection = db["resumes"]

# -------------------------
# LLM Prompt Template
# -------------------------

RESUME_GENERATION_PROMPT = """
You are a professional resume writer and ATS optimization engine.

Using the provided structured candidate profile and job description,
generate a clean, ATS-friendly resume in JSON format.

STRICT RULES:
- Output ONLY valid JSON
- No explanations, no markdown
- Do NOT invent experience or skills
- Quantify achievements ONLY if data supports it
- Keep language professional and concise

CRITICAL — LITERAL KEYWORD INCLUSION:
If the profile contains technical skills, you MUST include exact literal strings in the skills list.
Examples of literal keywords to preserve:
  - "Python"
  - "Flask"
  - "MongoDB"
  - "REST APIs"
  - "Backend Development"
  - "React"
  - "PostgreSQL"
  - etc.

DO NOT paraphrase or simplify skill names.
ATS systems rely on exact token matching.

===== MANDATORY JD ALIGNMENT RULE =====

A job description has been provided. Analyze the JD for required technical keywords.

For EACH keyword found in the JD that is semantically compatible with the candidate's profile:
1. If the candidate lists it explicitly → Include it verbatim in skills or project technologies
2. If the candidate does NOT list it but has related experience (e.g., CS/ML background):
   - MUST include it in the resume ONLY with these qualifiers:
     • "Familiar with {keyword}"
     • "Basic exposure to {keyword}"
     • "Academic experience with {keyword}"
   - Place these in either the summary or skills section
3. If the keyword is completely unrelated to the candidate's background → Omit it

VALIDATION RULE (NON-NEGOTIABLE):
- The response MUST include at least ONE literal keyword from the job description
- If the response contains ZERO JD keywords, the response is INVALID
- Check both the skills section AND project technologies for keywords

Example:
JD mentions: Python, Flask, MongoDB, REST APIs
Profile: CS student with ML focus
Expected resume MUST include:
  - Skills like "Python", "REST APIs"
  - Or mention in projects: "Flask", "MongoDB"
  - Or summary: "Familiar with Flask microframework"

Do NOT omit all JD keywords just because they're not listed in the profile.
This is a resume for a real job, not a generic template.

Required JSON structure:
{
  "summary": "",
  "skills": [
    { "category": "", "items": [] }
  ],
  "experience": [
    {
      "role": "",
      "organization": "",
      "duration": "",
      "bullets": []
    }
  ],
  "projects": [
    {
      "title": "",
      "bullets": [],
      "technologies": []
    }
  ],
  "education": [
    {
      "degree": "",
      "institution": "",
      "year": ""
    }
  ]
}

Candidate Profile:
{profile_json}

Target Job Description:
{job_description}
"""

# -------------------------
# Core generator
# -------------------------

def generate_resume_from_profile(profile_id: str, job_description: str | None = None):
    """
    Generate a resume from a stored profile.

    Args:
        profile_id (str): MongoDB profile ID
        job_description (str | None): Optional JD

    Returns:
        dict: JSON-serializable resume document
        
    Raises:
        ValueError: If profile not found, LLM fails, or resume is malformed
    """

    profile = get_profile_by_id(profile_id)
    if not profile:
        raise ValueError("Profile not found")

    structured_profile = profile.get("structured")
    if not structured_profile:
        raise ValueError("Profile has no structured data")

    prompt = (
        RESUME_GENERATION_PROMPT
        .replace("{profile_json}", json.dumps(structured_profile, indent=2))
        .replace(
            "{job_description}",
            job_description if job_description else "General entry-level software engineering role"
        )
    )

    llm_response = call_llm_router(
        prompt=prompt,
        task="resume_generation",
        use_simulation=False
    )

    try:
        resume_json = json.loads(llm_response)
    except json.JSONDecodeError as e:
        logger.error(f"[RESUME_GEN] LLM returned invalid JSON: {llm_response[:200]}")
        raise ValueError(f"LLM did not return valid JSON: {e}")

    # -------------------------
    # Populate header from structured profile and validate schema
    # -------------------------
    personal = structured_profile.get("personal", {}) if structured_profile else {}
    header_name = (
      personal.get("name") or personal.get("full_name") or personal.get("fullName") or ""
    )
    header = {
      "name": header_name,
      "email": personal.get("email", "") if personal else "",
      "phone": personal.get("phone", "") if personal else "",
      "location": personal.get("location", "") if personal else "",
    }

    # Also include common links (github, linkedin, portfolio) from structured profile
    links = structured_profile.get("links", {}) if isinstance(structured_profile, dict) else {}
    if links:
      header["github"] = links.get("github", "")
      header["linkedin"] = links.get("linkedin", "")
      header["portfolio"] = links.get("portfolio", "")

    if not header["name"] or not header["name"].strip():
      raise ValueError("Structured profile missing required personal.name for resume header")

    resume_json["header"] = header

    # Validate canonical schema now that header is present
    try:
      validate_resume_schema(resume_json)
      logger.info(f"[RESUME_GEN] Resume schema validated successfully")
    except ValueError as e:
      logger.error(f"[RESUME_GEN] Resume schema validation failed: {e}")
      logger.error(f"[RESUME_GEN] Received resume: {json.dumps(resume_json, indent=2)[:500]}")
      raise


    # -------------------------
    # ENFORCE JD KEYWORD ALIGNMENT
    # Extract JD keywords and verify at least one appears in the resume
    # -------------------------
    if job_description:
      from resume_schema import extract_text_for_matching, _extract_keywords

      try:
        # Extract resume text using canonical method
        resume_text = extract_text_for_matching(resume_json)

        # Extract JD keywords
        jd_keywords = _extract_keywords(job_description)

        if jd_keywords:
          # Check if ANY JD keyword appears in resume text
          resume_text_normalized = resume_text.lower()
          matched_keywords = [kw for kw in jd_keywords if kw in resume_text_normalized]

          if not matched_keywords:
            error_msg = (
              f"[RESUME_GEN] CRITICAL: ATS keyword alignment failure!\n"
              f"JD keywords extracted: {jd_keywords[:10]}\n"
              f"Resume text (first 200 chars): {resume_text[:200]}\n"
              f"ZERO keywords matched. This resume will have 0% ATS score."
            )
            logger.error(error_msg)
            raise ValueError(
              f"Resume generated without any JD keyword alignment. "
              f"JD keywords: {jd_keywords[:5]}, Resume has none of these. "
              f"This indicates incomplete resume generation."
            )

          logger.info(
            f"[RESUME_GEN] ✓ ATS alignment check passed: {len(matched_keywords)} keywords matched"
          )
          logger.info(f"[RESUME_GEN] Matched keywords: {matched_keywords}")
      except Exception as e:
        logger.error(f"[RESUME_GEN] Failed to validate ATS alignment: {e}")
        raise ValueError(f"ATS alignment validation failed: {e}")

    # Build document
    resume_document = {
        "profile_id": ObjectId(profile_id),
        "job_description": job_description,
        "resume": resume_json,
        "created_at": datetime.utcnow()
    }

    # ✅ INSERT MUST HAPPEN FIRST
    result = resumes_collection.insert_one(resume_document)
    logger.info(f"[RESUME_GEN] Stored resume {result.inserted_id}")

    # ✅ THEN RETURN WITH resume_id
    return {
        "resume_id": str(result.inserted_id),
        "profile_id": profile_id,
        "resume": resume_json,
        "created_at": resume_document["created_at"].isoformat()
    }

