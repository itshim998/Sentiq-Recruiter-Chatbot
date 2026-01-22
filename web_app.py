import os
import csv
from io import StringIO
from flask import Response
from flask import Flask, jsonify, render_template, request, redirect
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

# -------------------------------------------------
# CORS Configuration - Allow static frontend origins
# -------------------------------------------------
cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "https://recruiteriq.sentiqlabs.com,https://resumeiq.sentiqlabs.com,http://localhost:5173,http://localhost:3000"
).split(",")

CORS(app, resources={
    r"/api/*": {
        "origins": cors_origins,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

@app.route("/")
def home():
    return redirect("/upload")


# Initialize DB once on startup
init_db()


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
# Dashboard UI
# -------------------------------------------------
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


# -------------------------------------------------
# Debug helper (optional but useful)
# -------------------------------------------------
@app.route("/__routes")
def show_routes():
    return str(app.url_map)


# -------------------------------------------------
# App entry point (MUST BE LAST)
# -------------------------------------------------
@app.route("/upload")
def upload_page():
    return render_template("upload.html")

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
