import logging
import json
import re
from typing import Dict

from llm_adapter import call_llm_router


# ------------------------------
# Logger setup
# ------------------------------
logger = logging.getLogger("sentiq.recruiter")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ------------------------------
# Recruiter Agent
# ------------------------------
class RecruiterBot:
    def __init__(self, default_category: str = "recruiter"):
        """
        Recruiter domain agent.
        """
        self.default_category = default_category

    def analyze_fit(self, resume_text: str, job_description: str) -> dict:
        """
        Returns a structured, machine-parseable evaluation of candidate fit.
        """

        prompt = f"""
You are a strict recruiter evaluation engine.

Evaluate the candidate using the rubric below:
- Skills match: 40%
- Relevant experience: 30%
- Role alignment: 20%
- Red flags / gaps: -10% penalty if applicable

Rules:
- Output VALID JSON ONLY
- score must be an integer between 0 and 100
- pros: exactly 3 concise, constructive bullet points
- cons: exactly 3 constructive improvement areas
- rationale: max 2 sentences, polite and encouraging
- Do NOT mention rejection or hiring decisions

Return JSON in this exact schema:
{{
  "score": <int>,
  "pros": ["...", "...", "..."],
  "cons": ["...", "...", "..."],
  "rationale": "..."
}}

Resume:
----
{resume_text}
----

Job Description:
----
{job_description}
----
"""

        raw = call_llm_router(
            prompt=(
                "SYSTEM: You must respond with STRICTLY VALID JSON. "
                "No markdown, no explanations, no extra text.\n\n"
                + prompt
            ),
            category="recruiter_eval",
            use_simulation=False,
            prefer="gemini"
        )

        import json
        import re

        try:
            parsed = json.loads(raw)
            return parsed
        except Exception:
            match = re.search(r"\{.*\}", raw, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass

        #  Guaranteed return
        return {
            "score": 0,
            "pros": [],
            "cons": [],
            "rationale": "Evaluation could not be generated reliably."
        }

    def recommend_action(self, evaluation: dict) -> dict:
        """
        Internal-only decision logic.
        Safe against bad or missing evaluation input.
        """

        if not isinstance(evaluation, dict):
            return {
                "recommendation": "hold",
                "confidence": 0.5,
                "reason": "Evaluation data was incomplete or unavailable."
            }

        score = evaluation.get("score", 0)

        if score >= 75:
            return {
                "recommendation": "interview",
                "confidence": round(min(0.95, 0.8 + (score - 75) / 50), 2),
                "reason": "Candidate meets core requirements with strong overall alignment."
            }

        if score >= 60:
            return {
                "recommendation": "hold",
                "confidence": 0.6,
                "reason": "Candidate shows potential but does not clearly meet all requirements."
            }

        return {
            "recommendation": "reject",
            "confidence": round(min(0.9, 0.6 + (60 - score) / 60), 2),
            "reason": "Candidate does not sufficiently meet the role requirements."
        }




        # ---------- Strict parsing ----------
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass

        # ---------- Absolute fallback ----------
        logger.error("RecruiterBot.analyze_fit: Invalid model output")

        return {
            "score": 0,
            "pros": [],
            "cons": [],
            "rationale": "Evaluation failed due to invalid model output."
        }

    def draft_email(
        self,
        candidate_name: str,
        reason: str,
        tone: str = "professional",
        invite: bool = False
    ) -> str:
        """
        Drafts a recruiter-style email (interview invite or rejection).
        Short task → router may fall back to Groq automatically.
        """

        intent = "invite the candidate for an interview" if invite else "inform the candidate about the application outcome"

        prompt = f"""
Write a {tone} email to {candidate_name} to {intent}.

Context:
{reason}

Rules:
- Output VALID JSON ONLY
- score must be an integer between 0 and 100
- pros: exactly 3 concise, constructive bullet points
- cons: exactly 3 constructive improvement areas (no harsh or judgmental language)
- rationale: max 2 sentences, written politely and encouragingly
- Do NOT mention rejection, failure, or hiring decisions

"""

        try:
            response = call_llm_router(
                prompt=prompt,
                category="recruiter_email",
                use_simulation=False,
                prefer="groq"
            )
            return response.strip()
        except Exception:
            # Safe fallback (never crash upstream)
            if invite:
                return (
                    f"Subject: Interview Invitation\n\n"
                    f"Dear {candidate_name},\n\n"
                    f"Thank you for your application. We would like to invite you to the next stage of the interview process.\n\n"
                    f"{reason}\n\n"
                    f"Best regards,"
                )
            else:
                return (
                    f"Subject: Application Update\n\n"
                    f"Dear {candidate_name},\n\n"
                    f"Thank you for your interest. After careful consideration, we will not be proceeding further at this time.\n\n"
                    f"{reason}\n\n"
                    f"Best wishes,"
                )


# ------------------------------
# Local test (optional)
# ------------------------------
if __name__ == "__main__":
    bot = RecruiterBot()
    demo = bot.analyze_fit(
        "Python developer with ML internship experience.",
        "Looking for a junior ML engineer with Python skills."
    )
    print(demo)
