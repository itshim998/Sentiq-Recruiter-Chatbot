from pathlib import Path
from typing import List

from recruiter_agent import RecruiterBot
from validators import validate_text_field
from resume_parser import parse_text_file
from name_extractor import extract_candidate_name
from db import (
    make_fingerprint,
    find_candidate_by_fingerprint,
    insert_candidate,
    get_candidate
)


class ScreeningService:
    def __init__(self):
        self.bot = RecruiterBot()

    def screen_files(
        self,
        files: List[Path],
        job_description: str
    ) -> list[dict]:

        job_description = validate_text_field(
            job_description,
            "job_description"
        )

        results = []

        for file_path in files:
            try:
                resume_text = parse_text_file(file_path)
                resume_text = validate_text_field(
                    resume_text,
                    "resume_text"
                )
            except Exception as e:
                results.append({
                    "file": file_path.name,
                    "status": "invalid",
                    "error": str(e)
                })
                continue

            fingerprint = make_fingerprint(
                resume_text,
                job_description
            )

            existing_id = find_candidate_by_fingerprint(
                fingerprint
            )

            # ------------------------------
            # Duplicate candidate
            # ------------------------------
            if existing_id:
                candidate = get_candidate(existing_id)
                results.append({
                    "file": file_path.name,
                    "candidate_id": existing_id,
                    "candidate_name": candidate.get("candidate_name"),
                    "status": "reused",
                    "score": candidate.get("score"),
                    "recommendation": candidate.get("recommendation")
                })
                continue

            # ------------------------------
            # Name extraction (LLM-assisted)
            # ------------------------------
            name_data = extract_candidate_name(resume_text)
            candidate_name = name_data.get("name")

            # ------------------------------
            # Evaluation
            # ------------------------------
            evaluation = self.bot.analyze_fit(
                resume_text,
                job_description
            )

            decision = self.bot.recommend_action(
                evaluation
            )

            # ------------------------------
            # Insert new candidate
            # ------------------------------
            candidate_id = insert_candidate(
                resume_text=resume_text,
                job_description=job_description,
                evaluation=evaluation,
                decision=decision,
                fingerprint=fingerprint,
                candidate_name=candidate_name
            )

            results.append({
                "file": file_path.name,
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "status": "new",
                "score": evaluation.get("score"),
                "recommendation": decision.get("recommendation")
            })

        return results
