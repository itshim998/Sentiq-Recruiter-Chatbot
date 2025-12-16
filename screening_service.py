from recruiter_agent import RecruiterBot
from validators import validate_text_field
from db import (
    make_fingerprint,
    find_candidate_by_fingerprint,
    insert_candidate,
    get_candidate
)
from resume_parser import parse_text_file
from pathlib import Path

class ScreeningService:
    def __init__(self):
        self.bot = RecruiterBot()

    def screen_files(self, files: list[Path], job_description: str) -> list[dict]:
        job_description = validate_text_field(
            job_description,
            "job_description"
        )

        results = []

        for file_path in files:
            try:
                resume_text = parse_text_file(file_path)
                resume_text = validate_text_field(resume_text, "resume_text")
            except Exception as e:
                results.append({
                    "file": file_path.name,
                    "status": "invalid",
                    "error": str(e)
                })
                continue

            fingerprint = make_fingerprint(resume_text, job_description)
            existing_id = find_candidate_by_fingerprint(fingerprint)

            if existing_id:
                candidate = get_candidate(existing_id)
                results.append({
                    "file": file_path.name,
                    "candidate_id": existing_id,
                    "status": "reused",
                    "score": candidate["score"],
                    "recommendation": candidate["recommendation"]
                })
                continue

            evaluation = self.bot.analyze_fit(resume_text, job_description)
            decision = self.bot.recommend_action(evaluation)

            candidate_id = insert_candidate(
                resume_text=resume_text,
                job_description=job_description,
                evaluation=evaluation,
                decision=decision,
                fingerprint=fingerprint
            )

            results.append({
                "file": file_path.name,
                "candidate_id": candidate_id,
                "status": "new",
                "score": evaluation["score"],
                "recommendation": decision["recommendation"]
            })

        return results
