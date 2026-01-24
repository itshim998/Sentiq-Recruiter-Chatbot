"""
resume_schema.py
----------------
CANONICAL Resume Schema for ResumeIQ

This is the SINGLE SOURCE OF TRUTH for resume structure.
All modules (generation, ATS, PDF) must use ONLY this schema.

Any deviation = immediate exception (no silent fallbacks).
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import re


# ==========================================
# KEYWORD EXTRACTION (For ATS Alignment)
# ==========================================

def _extract_keywords(text: str) -> List[str]:
    """
    Extract potential ATS keywords from text (JD or resume).
    Returns list of unique keywords (3+ chars, non-stopword).
    """
    text = text.lower()
    # Replace non-alphanumeric with spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    
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


# ==========================================
# CANONICAL RESUME SCHEMA (STRICT)
# ==========================================

def validate_resume_schema(resume: Dict[str, Any]) -> None:
    """
    STRICT validation: Ensures resume matches canonical schema.
    
    Raises:
        ValueError: If resume is missing required fields or has wrong structure
    
    Canonical structure:
    {
        "summary": str (required, non-empty),
        "skills": List[str] (required, at least 1),
        "experience": List[Dict] (required, can be empty),
        "projects": List[Dict] (optional, can be empty),
        "education": List[Dict] (optional, can be empty)
    }
    """
    
    # ✅ Null/empty checks
    if not resume:
        raise ValueError("Resume is empty or None")
    
    if not isinstance(resume, dict):
        raise ValueError(f"Resume must be a dict, got {type(resume)}")
    
    # ✅ Required: header (personal information)
    if "header" not in resume:
        raise ValueError("Resume missing required field: 'header'")

    header = resume.get("header")
    if not isinstance(header, dict):
        raise ValueError(f"'header' must be an object, got {type(header)}")

    # header.name must be present and non-empty
    name = header.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("'header.name' is required and must be a non-empty string")

    # other header fields if present must be strings
    for f in ["email", "phone", "location"]:
        if f in header and header[f] is not None and not isinstance(header[f], str):
            raise ValueError(f"'header.{f}' must be a string if present")

    # ✅ Required: summary
    if "summary" not in resume:
        raise ValueError("Resume missing required field: 'summary'")
    
    summary = resume.get("summary")
    if not isinstance(summary, str):
        raise ValueError(f"'summary' must be string, got {type(summary)}")
    
    if not summary.strip():
        raise ValueError("'summary' cannot be empty")
    
    # ✅ Required: skills (at least 1)
    if "skills" not in resume:
        raise ValueError("Resume missing required field: 'skills'")
    
    skills = resume.get("skills")
    if not isinstance(skills, list):
        raise ValueError(f"'skills' must be a list, got {type(skills)}")
    
    # Skills can be strings OR dicts with "items" field
    for i, skill in enumerate(skills):
        if isinstance(skill, str):
            if not skill.strip():
                raise ValueError(f"'skills[{i}]' cannot be empty string")
        elif isinstance(skill, dict):
            if "items" in skill and isinstance(skill["items"], list):
                for j, item in enumerate(skill["items"]):
                    if not isinstance(item, str) or not item.strip():
                        raise ValueError(f"'skills[{i}].items[{j}]' must be non-empty string")
            elif "category" in skill and isinstance(skill.get("category"), str):
                if not skill["category"].strip():
                    raise ValueError(f"'skills[{i}].category' cannot be empty")
        else:
            raise ValueError(f"'skills[{i}]' must be string or dict, got {type(skill)}")
    
    if not skills or all(
        (isinstance(s, dict) and not s.get("items")) 
        for s in skills
    ):
        raise ValueError("Resume must have at least 1 skill")
    
    # ✅ Optional: experience (can be empty, but must be list)
    if "experience" not in resume:
        raise ValueError("Resume missing required field: 'experience'")
    
    experience = resume.get("experience")
    if not isinstance(experience, list):
        raise ValueError(f"'experience' must be a list, got {type(experience)}")
    
    for i, exp in enumerate(experience):
        if not isinstance(exp, dict):
            raise ValueError(f"'experience[{i}]' must be dict, got {type(exp)}")
        
        # Check required exp fields if present
        for field in ["role", "organization", "duration"]:
            if field in exp and not isinstance(exp[field], str):
                raise ValueError(f"'experience[{i}].{field}' must be string")
        
        if "bullets" in exp and not isinstance(exp["bullets"], list):
            raise ValueError(f"'experience[{i}].bullets' must be list")
    
    # ✅ Optional: projects
    if "projects" in resume:
        projects = resume.get("projects")
        if not isinstance(projects, list):
            raise ValueError(f"'projects' must be a list, got {type(projects)}")
        
        for i, proj in enumerate(projects):
            if not isinstance(proj, dict):
                raise ValueError(f"'projects[{i}]' must be dict, got {type(proj)}")
    
    # ✅ Optional: education
    if "education" in resume:
        education = resume.get("education")
        if not isinstance(education, list):
            raise ValueError(f"'education' must be a list, got {type(education)}")
        
        for i, edu in enumerate(education):
            if not isinstance(edu, dict):
                raise ValueError(f"'education[{i}]' must be dict, got {type(edu)}")


def canonicalize_skills(skills: List[Any]) -> List[str]:
    """
    Convert skills (which can be strings or dicts) into a flat list of strings.
    
    Examples:
    - "Python" → ["Python"]
    - {"category": "Languages", "items": ["Python", "JavaScript"]} 
      → ["Python", "JavaScript"]
    """
    result = []
    
    for skill in skills:
        if isinstance(skill, str):
            if skill.strip():
                result.append(skill.strip())
        elif isinstance(skill, dict):
            # Try extracting items list
            if "items" in skill and isinstance(skill["items"], list):
                for item in skill["items"]:
                    if isinstance(item, str) and item.strip():
                        result.append(item.strip())
            # Also add category if present
            if "category" in skill and isinstance(skill["category"], str):
                if skill["category"].strip():
                    result.append(skill["category"].strip())
    
    return result

def normalize_for_ats(text: str) -> str:
    """
    Normalize resume text for ATS matching.
    Expands multi-word skills into unigram-friendly tokens
    without mutating stored resume data.
    """
    if not isinstance(text, str):
        return ""

    expansions = {
        "machine learning": ["machine", "learning"],
        "artificial intelligence": ["artificial", "intelligence", "ai"],
        "web development": ["web", "development"],
        "data science": ["data", "science"],
        "computer vision": ["computer", "vision"],
    }

    for phrase, tokens in expansions.items():
        if phrase in text:
            text += " " + " ".join(tokens)

    return text


def extract_text_for_matching(resume: Dict[str, Any]) -> str:
    """
    Extract ALL text from resume into single normalized string for ATS matching.
    
    CRITICAL: This is the ONLY way ATS should build its matching text.
    
    Args:
        resume: Validated resume dict
    
    Returns:
        Normalized text string (lowercased, spaces normalized)
    """
    parts = []
    # Include header fields (name, location) for matching context, but DO NOT include email/phone
    header = resume.get("header", {})
    if isinstance(header, dict):
        if header.get("name"):
            parts.append(str(header.get("name")))
        if header.get("location"):
            parts.append(str(header.get("location")))
    
    # Summary
    if resume.get("summary"):
        parts.append(resume["summary"])
    
    # Skills (flatten both string and dict formats)
    for skill in resume.get("skills", []):
        if isinstance(skill, str):
            parts.append(skill)
        elif isinstance(skill, dict):
            if skill.get("category"):
                parts.append(str(skill["category"]))
            if skill.get("items"):
                parts.extend([str(i) for i in skill["items"] if i])
    
    # Experience
    for exp in resume.get("experience", []):
        if isinstance(exp, dict):
            for key in ["role", "organization", "duration"]:
                if exp.get(key):
                    parts.append(str(exp[key]))
            if exp.get("bullets"):
                parts.extend([str(b) for b in exp["bullets"] if b])
    
    # Projects
    for proj in resume.get("projects", []):
        if isinstance(proj, dict):
            if proj.get("title"):
                parts.append(str(proj["title"]))
            if proj.get("bullets"):
                parts.extend([str(b) for b in proj["bullets"] if b])
            if proj.get("technologies"):
                parts.extend([str(t) for t in proj["technologies"] if t])
    
    # Education
    for edu in resume.get("education", []):
        if isinstance(edu, dict):
            for key in ["degree", "institution", "year"]:
                if edu.get(key):
                    parts.append(str(edu[key]))
    
    # Normalize
    text = " ".join(parts).lower()
    # Collapse multiple spaces
    text = " ".join(text.split())
    
    return text
