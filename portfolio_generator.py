"""
portfolio_generator.py
----------------------
ResumeIQ — Portfolio Generation Engine

Responsibility:
- Generate a one-page, mobile-responsive portfolio website
- STRICTLY derived from a resume
- Persist portfolio HTML in MongoDB

CRITICAL RULES:
- resume_id is MANDATORY (non-negotiable)
- Primary source: resume["resume"] schema
- Secondary fallback: profile["structured"]
- NO invented data

NO ATS logic
NO parsing
NO PDF rendering
"""

from datetime import datetime
from typing import Dict, Any
import os

from bson import ObjectId
from dotenv import load_dotenv

from profile_repository import get_profile_by_id
from resume_repository import get_resume_by_id

# ------------------------------
# Environment & DB setup (shared single client)
# ------------------------------

load_dotenv()

from db import db

portfolios_collection = db["portfolios"]

# ------------------------------
# HTML Template
# ------------------------------

def generate_portfolio_html(
    resume: Dict[str, Any],
    profile: Dict[str, Any]
) -> str:
    """
    Generate a clean, responsive portfolio HTML page.
    
    PRIMARY DATA SOURCE: resume["resume"] (canonical schema)
    FALLBACK: profile["structured"]
    """

    # Extract from resume (primary source)
    resume_data = resume.get("resume", {})
    
    # Personal info
    personal = resume_data.get("personal", {})
    name = personal.get("name") or profile["structured"].get("personal", {}).get("name", "Portfolio")
    email = personal.get("email", "")
    phone = personal.get("phone", "")
    location = personal.get("location", "")
    
    # Summary
    summary = resume_data.get("summary", "")
    
    # Skills
    skills = resume_data.get("skills", [])
    if not skills:
        skills = profile["structured"].get("skills", [])
    
    # Projects
    projects = resume_data.get("projects", [])
    if not projects:
        projects = profile["structured"].get("projects", [])
    
    # Experience
    experience = resume_data.get("experience", [])
    if not experience:
        experience = profile["structured"].get("experience", [])
    
    # Education
    education = resume_data.get("education", [])
    if not education:
        education = profile["structured"].get("education", [])
    
    # Links
    links = resume_data.get("links", {})
    if not links:
        links = profile["structured"].get("links", {})

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} | Portfolio</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
  margin: 0;
  padding: 0;
  line-height: 1.6;
  background: #ffffff;
  color: #1a1a1a;
}}
header {{
  padding: 64px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  text-align: center;
}}
header h1 {{
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 8px;
}}
header p {{
  font-size: 1.1rem;
  opacity: 0.95;
  margin: 4px 0;
}}
.contact-links {{
  margin-top: 16px;
  font-size: 0.95rem;
}}
.contact-links a {{
  color: #fff;
  text-decoration: underline;
  margin: 0 12px;
}}
section {{
  padding: 48px 24px;
  max-width: 1000px;
  margin: auto;
}}
h2 {{
  font-size: 1.8rem;
  margin-bottom: 24px;
  color: #333;
  border-bottom: 3px solid #667eea;
  padding-bottom: 8px;
  display: inline-block;
}}
.skills-grid {{
  margin-top: 16px;
}}
.skill-category {{
  margin-bottom: 16px;
}}
.skill-category strong {{
  color: #555;
  font-size: 1rem;
}}
.skill {{
  display: inline-block;
  margin: 6px 8px 6px 0;
  padding: 8px 16px;
  border-radius: 20px;
  background: #f0f0f0;
  font-size: 0.9rem;
  color: #333;
  border: 1px solid #ddd;
}}
.card {{
  margin-bottom: 32px;
  padding: 20px;
  background: #fafafa;
  border-left: 4px solid #667eea;
  border-radius: 4px;
}}
.card h3 {{
  font-size: 1.3rem;
  color: #333;
  margin-bottom: 8px;
}}
.card p {{
  margin: 8px 0;
  color: #555;
}}
.card em {{
  color: #666;
  font-size: 0.9rem;
}}
.footer {{
  padding: 32px 24px;
  text-align: center;
  font-size: 0.9rem;
  color: #888;
  background: #f9f9f9;
  margin-top: 48px;
}}
@media (max-width: 768px) {{
  header h1 {{ font-size: 2rem; }}
  h2 {{ font-size: 1.5rem; }}
}}
</style>
</head>
<body>

<header>
  <h1>{name}</h1>
  {f"<p>{email}</p>" if email else ""}
  {f"<p>{phone} • {location}</p>" if phone or location else f"<p>{location}</p>" if location else ""}
  <div class="contact-links">
    {f'<a href="{links.get("github")}" target="_blank">GitHub</a>' if links.get("github") else ""}
    {f'<a href="{links.get("linkedin")}" target="_blank">LinkedIn</a>' if links.get("linkedin") else ""}
    {f'<a href="{links.get("portfolio")}" target="_blank">Website</a>' if links.get("portfolio") else ""}
  </div>
</header>

{f'''<section>
  <h2>About Me</h2>
  <p style="font-size: 1.05rem; line-height: 1.7; color: #444;">{summary}</p>
</section>''' if summary else ""}

<section>
  <h2>Skills</h2>
  <div class="skills-grid">
  {"".join(
      f"<div class='skill-category'><strong>{s.get('category', 'Skills')}:</strong> "
      + " ".join(f'<span class="skill">{item}</span>' for item in s.get('items', []))
      + "</div>"
      for s in skills
  ) if skills else "<p>No skills listed.</p>"}
  </div>
</section>

{f'''<section>
  <h2>Projects</h2>
  {"".join(
      f"<div class='card'>"
      f"<h3>{p.get('title', 'Untitled Project')}</h3>"
      f"<p>{p.get('description', '')}</p>"
      f"<p><em>Technologies:</em> {', '.join(p.get('technologies', []))}</p>"
      f"</div>"
      for p in projects
  )}
</section>''' if projects else ""}

{f'''<section>
  <h2>Experience</h2>
  {"".join(
      f"<div class='card'>"
      f"<h3>{e.get('role', 'Role')}</h3>"
      f"<p><strong>{e.get('organization', 'Company')}</strong> | {e.get('duration', '')}</p>"
      f"<p>{e.get('details', '')}</p>"
      f"</div>"
      for e in experience
  )}
</section>''' if experience else ""}

{f'''<section>
  <h2>Education</h2>
  {"".join(
      f"<div class='card'>"
      f"<h3>{ed.get('degree', 'Degree')}</h3>"
      f"<p><strong>{ed.get('institution', 'Institution')}</strong> | {ed.get('year', '')}</p>"
      f"</div>"
      for ed in education
  )}
</section>''' if education else ""}

<div class="footer">
  Generated by ResumeIQ • SentIQ AI Labs
</div>

</body>
</html>
"""
    
    # CRITICAL: Fail if HTML is suspiciously short (< 500 chars)
    if len(html) < 500:
        raise ValueError("Generated HTML is too short. Likely missing critical data.")
    
    return html


# ------------------------------
# Public API
# ------------------------------

def generate_portfolio(
    resume_id: str,
    profile_id: str
) -> Dict[str, Any]:
    """
    Generate and store a portfolio website.
    
    CRITICAL: resume_id is MANDATORY (non-negotiable)

    Args:
        resume_id: MongoDB resume ID (REQUIRED)
        profile_id: MongoDB profile ID

    Returns:
        Stored portfolio document

    Raises:
        ValueError: If resume or profile not found
    """

    # ENFORCE: resume_id is mandatory
    if not resume_id:
        raise ValueError("resume_id is required for portfolio generation")

    # Validate resume exists
    resume = get_resume_by_id(resume_id)
    if not resume:
        raise ValueError(f"Resume not found: {resume_id}")

    # Validate profile exists
    profile = get_profile_by_id(profile_id)
    if not profile:
        raise ValueError(f"Profile not found: {profile_id}")

    # Generate HTML (primary source: resume)
    html = generate_portfolio_html(resume, profile)

    # Store in MongoDB
    portfolio_doc = {
        "profile_id": ObjectId(profile_id),
        "resume_id": ObjectId(resume_id),
        "html": html,
        "created_at": datetime.utcnow()
    }

    result = portfolios_collection.insert_one(portfolio_doc)
    portfolio_doc["_id"] = str(result.inserted_id)
    portfolio_doc["profile_id"] = profile_id
    portfolio_doc["resume_id"] = resume_id
    
    # Convert datetime to ISO string for JSON serialization
    portfolio_doc["created_at"] = portfolio_doc["created_at"].isoformat()

    return portfolio_doc


# ------------------------------
# Optional local test
# ------------------------------

if __name__ == "__main__":
    TEST_PROFILE_ID = "PUT_PROFILE_ID_HERE"
    TEST_RESUME_ID = "PUT_RESUME_ID_HERE"
    portfolio = generate_portfolio(TEST_RESUME_ID, TEST_PROFILE_ID)
    print("Portfolio generated:", portfolio["_id"])
