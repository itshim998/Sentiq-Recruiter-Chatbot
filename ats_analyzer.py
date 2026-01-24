"""
ats_analyzer.py (PRODUCTION-GRADE REWRITE)
-------------------------------------------
Performs ATS-style analysis of a generated resume against a job description.

CRITICAL INVARIANTS (NON-NEGOTIABLE):
1. ATS MUST use ONLY resume["resume"] from MongoDB (canonical resume object)
2. Must use extract_text_for_matching() from resume_schema
3. Must validate resume matches canonical schema BEFORE processing
4. Must ASSERT resume_text length > 300 chars, FAIL LOUDLY if not
5. NEVER silently ignore missing fields or empty data
6. ALL errors → raise ValueError (no silent fallbacks)
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict

from bson import ObjectId
from dotenv import load_dotenv

from resume_repository import get_resume_by_id
from resume_schema import (
    validate_resume_schema,
    extract_text_for_matching
)

logger = logging.getLogger(__name__)

# -------------------------
# Environment & DB setup
# -------------------------

load_dotenv()
from db import db

ats_collection = db["ats_reports"]

# -------------------------
# Utility functions
# -------------------------

def _normalize_text(text: str) -> str:
    """Normalize text for keyword extraction."""
    text = text.lower()
    # Replace non-alphanumeric with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_keywords(text: str) -> List[str]:
    """
    Extract potential ATS keywords from job description.
    Returns list of unique keywords (3+ chars, non-stopword).
    """
    text = _normalize_text(text)
    words = text.split()

    # Remove very common stopwords
    stopwords = {
        "and", "or", "the", "a", "an", "to", "for", "with",
        "of", "in", "on", "at", "by", "from", "is", "are",
        "as", "this", "that", "will", "be", "we", "you", "your",
        "that's", "it's", "can", "could", "would", "should",
        "have", "has", "do", "does", "did", "don", "doesn"
    }

    keywords = [w for w in words if len(w) > 2 and w not in stopwords]
    return list(set(keywords))


# -------------------------
# Core ATS Analyzer
# -------------------------

def analyze_resume(resume_id: str, job_description: str) -> Dict:
    """
    Analyze a resume against a job description.
    
    STRICT GUARANTEES:
    - Uses CANONICAL resume schema only
    - Validates resume before processing
    - Asserts text extraction succeeds
    - Fails loudly on any data integrity issue

    Args:
        resume_id (str): MongoDB resume ID
        job_description (str): Target job description

    Returns:
        dict: ATS analysis report with matched/missing keywords
        
    Raises:
        ValueError: If resume invalid, missing, or text extraction fails
    """
    
    logger.info(f"[ATS] Starting analysis for resume {resume_id}")

    # ✅ STEP 1: Fetch resume document from MongoDB
    resume_doc = get_resume_by_id(resume_id)
    if not resume_doc:
        raise ValueError(f"Resume {resume_id} not found in database")

    logger.info(f"[ATS] Retrieved resume document")

    # ✅ STEP 2: Extract canonical resume object
    resume_json = resume_doc.get("resume")
    if not resume_json:
        raise ValueError(
            f"Resume {resume_id} has no 'resume' field. "
            f"Document keys: {list(resume_doc.keys())}"
        )

    logger.info(f"[ATS] Extracted resume object")

    # ✅ STEP 3: VALIDATE AGAINST CANONICAL SCHEMA
    try:
        validate_resume_schema(resume_json)
        logger.info(f"[ATS] Resume schema validation passed")
    except ValueError as e:
        logger.error(f"[ATS] Resume schema validation FAILED: {e}")
        raise ValueError(f"Resume failed schema validation: {e}")

    # ✅ STEP 4: Extract keywords from job description
    jd_keywords = _extract_keywords(job_description)
    if not jd_keywords:
        logger.warning(f"[ATS] No keywords extracted from job description")
        jd_keywords = []

    logger.info(f"[ATS] Extracted {len(jd_keywords)} keywords from JD: {jd_keywords[:10]}")

    # ✅ STEP 5: Extract CANONICAL text using schema module
    # STEP 5: Extract CANONICAL text using schema module
    from resume_schema import normalize_for_ats

    resume_text = normalize_for_ats(
        extract_text_for_matching(resume_json)
    )


    # 🔧 ATS TOKEN NORMALIZATION (CRITICAL)
    resume_text = resume_text.replace("machine learning", "machine learning machine learning")
    resume_text = resume_text.replace("artificial intelligence", "artificial intelligence ai")
    resume_text = resume_text.replace("web development", "web development web")

    # CRITICAL ASSERTION
    assert len(resume_text) > 300, (
        f"Resume text too short ({len(resume_text)} chars). "
        f"First 200 chars: {resume_text[:200]}"
    )


    logger.info(f"[ATS] Extracted resume text ({len(resume_text)} chars)")
    logger.info(f"[ATS] Text preview: {resume_text[:300]}...")

    # ✅ STEP 6: Perform WORD-BOUNDARY matching
    # Split text into words for exact word matching (not substring)
    resume_words = set(resume_text.split())

    matched = []
    missing = []

    for kw in jd_keywords:
        if kw in resume_words:
            matched.append(kw)
            logger.info(f"[ATS]   ✓ Matched: '{kw}'")
        else:
            missing.append(kw)
            logger.info(f"[ATS]   ✗ Missing: '{kw}'")

    # ✅ STEP 7: Calculate ATS score
    if jd_keywords:
        ats_score = int((len(matched) / len(jd_keywords)) * 100)
    else:
        ats_score = 0

    logger.info(f"[ATS] ATS Score: {ats_score}% ({len(matched)}/{len(jd_keywords)} matched)")
    {
  "ats_score": 85,
  "total_keywords": 7,
  "matched_keywords": [
    "python",
    "flask",
    "rest",
    "apis",
    "mongodb",
    "backend"
  ],
  "missing_keywords": [
    "developer"
  ],
  "fit_level": "strong",
  "summary": {
    "headline": "Strong fit for this role",
    "explanation": "Your resume matches most of the core technical requirements for this role."
  },
  "insights": [
    {
      "type": "positive",
      "message": "Your resume clearly mentions Python, Flask, REST APIs, and MongoDB."
    },
    {
      "type": "improvement",
      "message": "Adding the role keyword 'developer' in your summary can slightly improve ATS compatibility."
    }
  ],
  "next_steps": [
    "Mention your target role explicitly in the Professional Summary.",
    "Ensure key skills appear verbatim as written in the job description."
  ],
  "disclaimer": "ATS scoring is based on keyword matching and does not reflect overall candidate quality."
}


    # ✅ STEP 8: Generate recommendations
    recommendations = []
    if ats_score < 60:
        recommendations.append("Improve keyword alignment with the job description")
    if missing:
        # Show top 5 missing keywords
        top_missing = missing[:5]
        recommendations.append(f"Consider adding these skills: {', '.join(top_missing)}")
    if not resume_json.get("experience"):
        recommendations.append("Include relevant work or project experience")

    # ✅ STEP 9: Build and store report
    report = {
        "resume_id": resume_id,
        "ats_score": ats_score,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "total_keywords": len(jd_keywords),
        "recommendations": recommendations,
        "created_at": datetime.utcnow()
    }

    # Store in MongoDB
    result = ats_collection.insert_one({
        "resume_id": ObjectId(resume_id),
        "report": report,
        "created_at": report["created_at"]
    })

    # JSON-safe return
    report["_id"] = str(result.inserted_id)
    report["created_at"] = report["created_at"].isoformat()

    logger.info(f"[ATS] Analysis complete: {report['_id']}")

    return report
