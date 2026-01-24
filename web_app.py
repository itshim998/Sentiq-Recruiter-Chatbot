import os
import csv
from io import StringIO
from flask import Response
from flask import Flask, jsonify, request
from flask_cors import CORS

# --- Core backend imports ---
from db import (
    init_db,
    list_candidates,
    get_candidate
)
from screening_service import ScreeningService
from storage import save_upload

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)

# ============================================================================
# CORS CONFIGURATION - PRODUCTION CROSS-ORIGIN SETUP
# ============================================================================
# CRITICAL: Frontend is now hosted on Hostinger (https://resumeiqv1.sentiqlabs.com)
# Backend is API-only on Render (https://recruiteriq.sentiqlabs.com)
# This is a cross-origin architecture requiring explicit CORS headers.
# ============================================================================

# Production origins - explicitly list all allowed frontends
PRODUCTION_ORIGINS = [
    "https://resumeiqv1.sentiqlabs.com",   # Primary frontend on Hostinger
    "https://resumeiq.sentiqlabs.com",      # Alternate frontend domain
    "https://recruiteriq.sentiqlabs.com",   # RecruiterIQ frontend
]

# Development origins - for local testing
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:5000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
]

# Allow override via environment variable (comma-separated)
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
if cors_origins_env:
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    cors_origins = PRODUCTION_ORIGINS + DEV_ORIGINS

# Apply CORS globally to all /api/* routes
CORS(
    app,
    resources={r"/api/*": {"origins": cors_origins}},
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
    expose_headers=["Content-Disposition"],
    supports_credentials=True,
    max_age=3600
)

# Initialize DB once on startup
init_db()


# -------------------------------------------------
# Root endpoint - API status
# -------------------------------------------------
@app.route("/")
def root():
    return jsonify({
        "service": "RecruiterIQ API",
        "status": "running",
        "frontend": "https://recruiteriq.sentiqlabs.com"
    })


# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.route("/ping")
def ping():
    return ("ok", 200, {"Content-Type": "text/plain"})


# -------------------------------------------------
# Dashboard APIs (read-only)
# -------------------------------------------------
@app.route("/api/dashboard/candidates", methods=["GET"])
def dashboard_candidates():
    return jsonify(list_candidates())


@app.route("/api/dashboard/candidate/<int:candidate_id>", methods=["GET"])
def dashboard_candidate_detail(candidate_id):
    candidate = get_candidate(candidate_id)
    if not candidate:
        return jsonify({"error": "Not found"}), 404
    return jsonify(candidate)
@app.route("/api/dashboard/clear", methods=["POST"])
def clear_dashboard():
    from db import delete_all_candidates
    delete_all_candidates()
    return jsonify({"status": "ok"})


# -------------------------------------------------
# Resume upload + batch screening API
# -------------------------------------------------
@app.route("/api/screen/upload", methods=["POST"])
def upload_and_screen():
    job_description = request.form.get("job_description")
    files = request.files.getlist("resumes")
    MAX_RESUMES = 30

    if len(files) > MAX_RESUMES:
        return jsonify({
            "error": f"Batch limit exceeded. Maximum {MAX_RESUMES} resumes allowed per upload."
        }), 400


    if not job_description or not files:
        return jsonify({"error": "Missing job description or resumes"}), 400

    service = ScreeningService()
    saved_paths = []

    for f in files:
        try:
            path = save_upload(f.read(), f.filename)
            saved_paths.append(path)
        except Exception as e:
            return jsonify({
                "error": f"Failed to save file {f.filename}",
                "detail": str(e)
            }), 400

    results = service.screen_files(saved_paths, job_description)
    return jsonify(results)


# -------------------------------------------------
# Debug helper (optional but useful)
# -------------------------------------------------
@app.route("/__routes")
def show_routes():
    return str(app.url_map)


# -------------------------------------------------
# Export API
# -------------------------------------------------
@app.route("/api/export/candidates", methods=["GET"])
def export_candidates_csv():
    candidates = list_candidates(limit=10_000)

    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID",
        "Score",
        "Recommendation",
        "Confidence",
        "Created At"
    ])

    # Rows
    for c in candidates:
        writer.writerow([
            c["id"],
            c["score"],
            c["recommendation"],
            c["confidence"],
            c["created_at"]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = (
        "attachment; filename=candidates_export.csv"
    )

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
