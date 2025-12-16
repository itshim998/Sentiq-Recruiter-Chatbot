import os
import csv
from io import StringIO
from flask import Response
from flask import Flask, jsonify, render_template, request

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

# Initialize DB once on startup
init_db()


# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.route("/ping")
def ping():
    return "ok"


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


# -------------------------------------------------
# Resume upload + batch screening API
# -------------------------------------------------
@app.route("/api/screen/upload", methods=["POST"])
def upload_and_screen():
    job_description = request.form.get("job_description")
    files = request.files.getlist("resumes")

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
