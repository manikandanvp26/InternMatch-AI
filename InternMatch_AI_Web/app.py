from pathlib import Path
import uuid

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

import engine

BASE = Path(__file__).resolve().parent
MAX_UPLOAD_MB = 150
PAGE_SIZE = 50

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# Only the most recent upload is kept in memory, so the server stays within a reasonable size.
CURRENT_JOB = {}


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/analyze")
def analyze():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify(error="Choose a file to upload."), 400
    try:
        df = engine.parse_upload(upload.filename, upload.read())
        result = engine.analyse(df)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    preview = request.args.get("preview") == "1"  # used for the sample on the home page; not stored
    job_id = None if preview else uuid.uuid4().hex
    if not preview:
        CURRENT_JOB.clear()
        CURRENT_JOB[job_id] = {"filename": upload.filename, **result}
    first = engine.page_rows(result, page=1, size=PAGE_SIZE)
    return jsonify(job_id=job_id, filename=upload.filename, summary=result["summary"], results=first)


@app.get("/api/results/<job_id>")
def results(job_id):
    job = CURRENT_JOB.get(job_id)
    if job is None:
        return jsonify(error="These results have expired. Upload the file again."), 404
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", PAGE_SIZE, type=int)
    status = request.args.get("status", "all")
    return jsonify(engine.page_rows(job, page=page, size=size, status=status))


@app.get("/api/export/<job_id>")
def export(job_id):
    job = CURRENT_JOB.get(job_id)
    if job is None:
        return jsonify(error="These results have expired. Upload the file again."), 404
    filename = "internmatch_results.csv"
    return Response(
        engine.export_lines(job),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )




@app.post("/api/profile-analyze")
def profile_analyze():
    """Analyse one student from the manual profile form using the same ML pipeline."""
    payload = request.get_json(silent=True) or {}
    required = ["student_name", "education", "domain_interest", "career_goal",
                "experience_level", "skills"]
    missing = [field for field in required if not str(payload.get(field, "")).strip()]
    if missing:
        return jsonify(error="Please complete these fields: " + ", ".join(missing)), 400
    try:
        frame = engine.pd.DataFrame([payload])
        result = engine.analyse(frame)
        student = result["rows"][0]
        if student["status"] == "Needs fix":
            return jsonify(error="Please check the profile values: " + "; ".join(student["errors"])), 400
        output = engine.public_row(student)
        return jsonify(student=output)
    except Exception as exc:
        app.logger.exception("Profile analysis failed")
        return jsonify(error=f"Could not analyse this profile: {exc}"), 500


@app.post("/api/profile-report")
def profile_report():
    """Create a PDF report for one analysed student."""
    payload = request.get_json(silent=True) or {}
    student = payload.get("student") or {}
    if not student.get("predicted_category"):
        return jsonify(error="Analyse a student profile before downloading the report."), 400

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TealTitle", parent=styles["Title"], textColor=colors.HexColor("#087F78")))
    styles.add(ParagraphStyle(name="SmallMuted", parent=styles["BodyText"], textColor=colors.HexColor("#64748B"), fontSize=8))
    story = [
        Paragraph("InternMatch AI", styles["TealTitle"]),
        Paragraph("Personal Internship Recommendation Report", styles["Heading2"]),
        Spacer(1, 6*mm),
    ]
    fields = [
        ["Student", student.get("student_name", "")],
        ["Education", student.get("education", "")],
        ["Domain interest", student.get("domain_interest", "")],
        ["Career goal", student.get("career_goal", "")],
        ["Preferred location", student.get("preferred_location", "")],
        ["Maximum duration", f'{student.get("preferred_duration_months", 6)} month(s)'],
        ["Predicted category", student.get("predicted_category", "")],
        ["Model confidence", f'{student.get("confidence", 0)}%'],
        ["Best listing match", f'{student.get("match_score", 0)}%'],
    ]
    safe_fields = [[Paragraph(str(a), styles["BodyText"]), Paragraph(str(b), styles["BodyText"])] for a,b in fields]
    profile_table = Table(safe_fields, colWidths=[48*mm, 115*mm])
    profile_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#E8F5F3")),
        ("TEXTCOLOR", (0,0), (0,-1), colors.HexColor("#176B66")),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#DCE7E5")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story += [profile_table, Spacer(1, 5*mm),
              Paragraph("Student skills", styles["Heading2"]),
              Paragraph(", ".join(student.get("skills", [])) or "Not provided", styles["BodyText"]),
              Spacer(1, 4*mm),
              Paragraph("Recommended internships", styles["Heading2"])]
    recommendations = student.get("recommended", [])
    if recommendations:
        rec_data = [["Role", "Company", "Match", "Location"]]
        for item in recommendations:
            rec_data.append([
                Paragraph(str(item.get("title", "")), styles["BodyText"]),
                Paragraph(str(item.get("company", "")), styles["BodyText"]),
                f'{item.get("match_score", 0)}%',
                Paragraph(str(item.get("location", "")), styles["BodyText"])
            ])
        rec_table = Table(rec_data, colWidths=[52*mm, 42*mm, 20*mm, 49*mm], repeatRows=1)
        rec_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#087F78")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#DCE7E5")),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(rec_table)
    else:
        story.append(Paragraph("No listings match the selected location and duration.", styles["BodyText"]))

    gaps = student.get("missing_skills", [])
    story += [Spacer(1, 5*mm), Paragraph("Skill gap analysis", styles["Heading2"]),
              Paragraph(", ".join(gaps) if gaps else "No missing skills found in the top recommendations.", styles["BodyText"]),
              Spacer(1, 6*mm),
              Paragraph("Note: Model confidence is not a hiring probability. Match score is a rule-based comparison against the internship listings bundled with this project. Always verify listing status on the source website.", styles["SmallMuted"])]
    doc.build(story)
    buffer.seek(0)
    return Response(buffer.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="InternMatch_AI_Student_Report.pdf"'})



@app.get("/api/listings")
def listings():
    return jsonify(engine.public_listings())


@app.get("/api/evaluation")
def evaluation():
    return jsonify(engine.evaluation())


@app.get("/api/template")
def template():
    return send_from_directory(BASE / "static", "sample_template.csv", as_attachment=True)


@app.errorhandler(RequestEntityTooLarge)
def too_large(_exc):
    return jsonify(error=f"This file is larger than the {MAX_UPLOAD_MB} MB limit."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000)
