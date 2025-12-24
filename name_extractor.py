from llm_adapter import call_llm_router
import json
import re

def extract_candidate_name(resume_text: str) -> dict:
    """
    Returns:
    {
      "name": str | None,
      "confidence": float
    }
    """

    prompt = f"""
Extract the candidate's full name from the resume text.

Rules:
- ONLY return a name if it is explicitly mentioned
- Do NOT guess
- If unclear, return null
- Confidence must reflect certainty

Return STRICT JSON only:
{{
  "name": string | null,
  "confidence": number between 0 and 1
}}

Resume:
----
{resume_text[:3000]}
----
"""

    raw = call_llm_router(
        prompt=prompt,
        category="recruiter_name",
        use_simulation=False,
        prefer="gemini"
    )

    try:
        data = json.loads(raw)
        name = data.get("name")
        confidence = float(data.get("confidence", 0))

        if not name or confidence < 0.85:
            return {"name": None, "confidence": confidence}

        # safety: basic sanity check
        if len(name.split()) > 4:
            return {"name": None, "confidence": 0}

        return {"name": name.strip(), "confidence": confidence}

    except Exception:
        return {"name": None, "confidence": 0}
