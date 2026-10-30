"""Reads uploaded student files, runs the Decision Tree model and ranks internships.

The ranking rules are the same as the original Streamlit app:
skill overlap (75 points) plus a bonus when the listing matches the predicted category (25 points).
"""
from collections import Counter
from pathlib import Path
import csv
import io
import json
import re

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
MODEL_PATH = ROOT / "models" / "decision_tree_pipeline.joblib"

EDUCATION = ["B.Tech CSE", "B.Tech IT", "B.Sc Computer Science", "BCA", "MCA", "B.Tech ECE", "B.Tech AI & DS"]
DOMAINS = ["Data Analytics", "Machine Learning", "Python Development", "Web Development",
           "Software Testing", "Cybersecurity", "Cloud Computing", "Product Management"]
GOALS = ["Data Analyst", "ML Engineer", "Python Developer", "Web Developer", "QA Engineer",
         "Security Analyst", "Cloud Engineer", "Undecided"]
EXPERIENCE = ["None", "College project", "Internship", "Freelance"]
LOCATIONS = ["Any", "Chennai", "Remote", "Bangalore", "Hybrid"]

FIELD_OPTIONS = {"education": EDUCATION, "domain_interest": DOMAINS, "career_goal": GOALS,
                 "experience_level": EXPERIENCE}

MAX_DURATION_MONTHS = 6          # same default as the original slider
MAX_ROWS = 200_000
TOP_LISTINGS = 3
PROBLEM_SAMPLE = 50              # how many row problems to list in the summary

TEMPLATE_COLUMNS = [
    "student_name", "education", "domain_interest", "career_goal", "projects_count",
    "certifications_count", "experience_level", "skills_count", "skills", "preferred_location",
]

# Other names people commonly use in their files -> the standard column name
COLUMN_ALIASES = {
    "name": "student_name", "full_name": "student_name", "student": "student_name",
    "student_full_name": "student_name", "domain": "domain_interest", "goal": "career_goal",
    "career": "career_goal", "project_count": "projects_count", "projects": "projects_count",
    "certification_count": "certifications_count", "certifications": "certifications_count",
    "experience": "experience_level", "skill": "skills", "skill_set": "skills",
    "technical_skills": "skills", "location": "preferred_location", "preferred_loc": "preferred_location",
}

SKILL_ALIASES = {"scikit learn": "scikit-learn", "powerbi": "power bi", "ml": "machine learning"}


def _split_skills(text):
    return [s.strip() for s in re.split(r"[,;|]", str(text)) if s.strip()]


def _norm_skill(text):
    text = " ".join(str(text).lower().strip().split())
    return SKILL_ALIASES.get(text, text)


def _load_value_map():
    path = DATA_DIR / "value_map.json"
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {field: {k.lower().strip(): v for k, v in raw.get(field, {}).items()} for field in FIELD_OPTIONS}


VALUE_MAP = _load_value_map()


# ---------- Model and listings (loaded once) ----------
_bundle = None


def _model_bundle():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def _load_listings():
    df = pd.read_csv(DATA_DIR / "internships.csv", encoding="utf-8-sig").fillna("")
    df["duration_months"] = pd.to_numeric(df["duration_months"], errors="coerce").fillna(3)
    records = []
    for row in df.to_dict("records"):
        required_raw = _split_skills(row.get("required_skills", ""))
        records.append({
            "title": str(row.get("title", "")),
            "company": str(row.get("company", "")),
            "category": str(row.get("category", "")),
            "location": str(row.get("location", "")),
            "work_mode": str(row.get("work_mode", "")),
            "duration_months": int(row["duration_months"]),
            "required_skills": str(row.get("required_skills", "")),
            "required_raw": required_raw,
            "required_norm": {_norm_skill(s) for s in required_raw},
            "source_type": str(row.get("source_type", "")),
            "source_checked": str(row.get("source_checked", "")),
            "source_url": str(row.get("source_url", "")),
        })
    return records


LISTINGS = _load_listings()


def _eligible_listings(preferred_location, max_duration_months=MAX_DURATION_MONTHS):
    items = [r for r in LISTINGS if r["duration_months"] <= max_duration_months]
    if preferred_location != "Any":
        pref = preferred_location.lower()
        items = [r for r in items if pref in r["location"].lower() or pref in r["work_mode"].lower()]
    return items


def _rank_for_student(skills, predicted, preferred_location, max_duration_months=MAX_DURATION_MONTHS):
    user = {_norm_skill(s) for s in skills}
    ranked = []
    for r in _eligible_listings(preferred_location, max_duration_months):
        ratio = len(user & r["required_norm"]) / len(r["required_norm"]) if r["required_norm"] else 0.0
        bonus = 0.25 if r["category"] == predicted else 0.0
        score = min(100.0, round(ratio * 75 + bonus * 100, 1))
        missing = [s for s in r["required_raw"] if _norm_skill(s) not in user]
        ranked.append((
            (score, r["category"] == predicted),
            {"title": r["title"], "company": r["company"], "location": r["location"],
             "work_mode": r["work_mode"], "duration_months": r["duration_months"],
             "category": r["category"], "match_score": score, "missing_skills": missing,
             "source_url": r["source_url"]},
        ))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in ranked]


def public_listings():
    return {
        "count": len(LISTINGS),
        "items": [{k: v for k, v in r.items() if k not in ("required_raw", "required_norm")} for r in LISTINGS],
    }


def evaluation():
    path = RESULTS_DIR / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ---------- Reading files of any supported format ----------
def _decode(data):
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("The text file could not be decoded.")


def _read_delimited(data, sep_override=None):
    text = _decode(data)
    if sep_override:
        sep = sep_override
    else:
        try:
            sep = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
        except csv.Error:
            sep = ","
    return pd.read_csv(io.StringIO(text), sep=sep, low_memory=False)


def parse_upload(filename, data):
    """Turn an uploaded file (CSV, TSV, TXT, Excel, JSON or XML) into a DataFrame."""
    ext = Path(filename).suffix.lower()
    if not data.strip():
        raise ValueError("The file is empty.")
    try:
        if ext in (".xlsx", ".xlsm", ".xls"):
            df = pd.read_excel(io.BytesIO(data))  # first sheet
        elif ext == ".json":
            payload = json.loads(_decode(data))
            if isinstance(payload, dict):
                lists = [v for v in payload.values() if isinstance(v, list)]
                payload = lists[0] if lists else [payload]
            df = pd.json_normalize(payload)
        elif ext == ".xml":
            df = pd.read_xml(io.BytesIO(data))
        elif ext in (".csv", ".tsv", ".txt"):
            df = _read_delimited(data, "\t" if ext == ".tsv" else None)
        else:
            raise ValueError(f"'{ext or 'this file'}' is not supported. Use CSV, TSV, Excel (.xlsx/.xls), JSON or XML.")
    except ValueError as exc:
        if str(exc).startswith("'") or "could not be decoded" in str(exc):
            raise
        raise ValueError(f"Could not read this file: {exc}") from exc
    except Exception as exc:  # corrupt Excel files and similar
        raise ValueError(f"Could not read this file: {exc}") from exc

    df = df.dropna(how="all")
    if df.empty:
        raise ValueError("The file has no student rows.")
    return df


def _normalise_columns(df):
    df = df.copy()
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})
    return df.loc[:, ~df.columns.duplicated()]


# ---------- Cleaning values ----------
def _text(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def _choice(value, field):
    """Return (canonical value, original text if it was mapped, or None if it could not be matched)."""
    text = _text(value)
    if not text:
        return None, None
    options = FIELD_OPTIONS[field]
    for option in options:
        if option.lower() == text.lower():
            return option, None
    mapped = VALUE_MAP[field].get(text.lower())
    if mapped in options:
        return mapped, text
    return None, None


def _number(value):
    """Blank -> 0. Returns None when the text is not a number."""
    text = _text(value)
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return None


def _status_for(score):
    if score >= 75:
        return "High Match"
    if score >= 50:
        return "Good Match"
    return "Explore"


def _build_record(raw, idx):
    """Validate one row. Returns (record, errors, mapped_values)."""
    name = _text(raw.get("student_name")) or f"Student {idx + 1}"
    errors, mapped = [], []

    def field_value(column, field, default=None):
        text = _text(raw.get(column)) or (default or "")
        value, original = _choice(text, field)
        if original:
            mapped.append(f"{field}: '{original}' → '{value}'")
        if not value:
            errors.append(f"{column} '{text or 'blank'}' is not recognised")
        return value

    education = field_value("education", "education")
    domain = field_value("domain_interest", "domain_interest")
    goal = field_value("career_goal", "career_goal")
    experience = field_value("experience_level", "experience_level", default="None")

    projects = _number(raw.get("projects_count"))
    if projects is None:
        errors.append("projects_count must be a number")
    certs = _number(raw.get("certifications_count"))
    if certs is None:
        errors.append("certifications_count must be a number")

    skills = _split_skills(_text(raw.get("skills")))
    skills_count = _number(raw.get("skills_count"))
    if skills_count is None:
        errors.append("skills_count must be a number")
    elif not _text(raw.get("skills_count")):
        skills_count = float(len(skills))

    preferred = _text(raw.get("preferred_location")) or "Any"
    if preferred not in LOCATIONS:
        preferred = next((loc for loc in LOCATIONS if loc.lower() == preferred.lower()), "Any")

    duration = _number(raw.get("preferred_duration_months"))
    if duration is None or duration < 1 or duration > 24:
        duration = MAX_DURATION_MONTHS
    duration = int(duration)

    record = {
        "row": idx + 2,  # +2 = the header line plus 1-based numbering
        "student_name": name,
        "education": education or _text(raw.get("education")),
        "domain_interest": domain or _text(raw.get("domain_interest")),
        "career_goal": goal or _text(raw.get("career_goal")),
        "experience_level": experience or _text(raw.get("experience_level")),
        "projects_count": int(projects or 0),
        "certifications_count": int(certs or 0),
        "skills_count": int(skills_count or 0),
        "skills": skills,
        "preferred_location": preferred,
        "preferred_duration_months": duration,
        "status": "Needs fix" if errors else "",
        "errors": errors,
        "predicted_category": None,
        "confidence": None,
        "match_score": None,
        "missing_skills": [],
    }
    return record, errors, mapped


def analyse(df):
    """Validate every row, run the model on the valid rows and score them.

    Recommendations are not stored for every student (that would use too much memory).
    `details()` calculates them when a row is shown or exported.
    """
    bundle = _model_bundle()
    model, features = bundle["model"], bundle["features"]

    df = _normalise_columns(df)
    columns_found = [c for c in TEMPLATE_COLUMNS if c in df.columns]
    columns_missing = [c for c in TEMPLATE_COLUMNS if c not in df.columns]
    truncated = len(df) > MAX_ROWS
    df = df.head(MAX_ROWS)

    rows, valid, problems, mapped_counts = [], [], [], Counter()
    problem_total = 0
    for idx, raw in enumerate(df.to_dict("records")):
        record, errors, mapped = _build_record(raw, idx)
        mapped_counts.update(mapped)
        if errors:
            problem_total += 1
            if len(problems) < PROBLEM_SAMPLE:
                problems.append(f"Row {record['row']} ({record['student_name']}): " + "; ".join(errors))
        else:
            valid.append(len(rows))
        rows.append(record)

    if valid:
        X = pd.DataFrame([{f: rows[i][f] for f in features} for i in valid])[features]
        predictions = model.predict(X)
        confidences = model.predict_proba(X).max(axis=1)
        for pos, i in enumerate(valid):
            record = rows[i]
            predicted = str(predictions[pos])
            top = _rank_for_student(
                record["skills"], predicted, record["preferred_location"],
                record.get("preferred_duration_months", MAX_DURATION_MONTHS)
            )[:TOP_LISTINGS]
            best = top[0]["match_score"] if top else 0.0
            gaps, seen = [], set()
            for item in top:
                for skill in item["missing_skills"]:
                    if _norm_skill(skill) not in seen:
                        seen.add(_norm_skill(skill))
                        gaps.append(skill)
            record.update({
                "status": _status_for(best),
                "predicted_category": predicted,
                "confidence": round(float(confidences[pos]) * 100, 1),
                "match_score": best,
                "missing_skills": gaps[:6],
            })

    analysed_rows = [r for r in rows if r["status"] != "Needs fix"]
    gap_counts = Counter(skill for r in analysed_rows for skill in r["missing_skills"])
    category_counts = Counter(r["predicted_category"] for r in analysed_rows)
    status_counts = Counter(r["status"] for r in analysed_rows)

    summary = {
        "total_rows": len(rows),
        "analysed": len(analysed_rows),
        "needs_fix": len(rows) - len(analysed_rows),
        "categories": [[k, v] for k, v in category_counts.most_common()],
        "statuses": {"High Match": status_counts.get("High Match", 0),
                     "Good Match": status_counts.get("Good Match", 0),
                     "Explore": status_counts.get("Explore", 0)},
        "listings": len(LISTINGS),
        "avg_match": round(float(np.mean([r["match_score"] for r in analysed_rows])), 1) if analysed_rows else 0.0,
        "high_match": status_counts.get("High Match", 0),
        "top_gaps": [[k, v] for k, v in gap_counts.most_common(10)],
        "columns_found": columns_found,
        "columns_missing": columns_missing,
        "truncated": truncated,
        "max_rows": MAX_ROWS,
        "problems": problems,
        "problem_total": problem_total,
        "mapped_values": [[k, v] for k, v in mapped_counts.most_common(15)],
        "mapped_total": sum(mapped_counts.values()),
    }
    return {"summary": summary, "rows": rows}


def details(row):
    """Top recommended listings for one analysed row (calculated on demand)."""
    if row["status"] == "Needs fix":
        return {"recommended": [], "recommended_count": 0}
    top = _rank_for_student(
        row["skills"], row["predicted_category"], row["preferred_location"],
        row.get("preferred_duration_months", MAX_DURATION_MONTHS)
    )[:TOP_LISTINGS]
    return {"recommended": top, "recommended_count": len(top)}


def public_row(row):
    """A row as the web page and CSV export show it."""
    out = {k: v for k, v in row.items() if k != "errors"}
    out["errors"] = row["errors"]
    out.update(details(row))
    return out


def page_rows(job, page=1, size=50, status="all"):
    rows = job["rows"]
    if status == "fix":
        rows = [r for r in rows if r["status"] == "Needs fix"]
    elif status == "ok":
        rows = [r for r in rows if r["status"] != "Needs fix"]
    size = min(max(size, 1), 200)
    pages = max(1, -(-len(rows) // size))
    page = min(max(page, 1), pages)
    start = (page - 1) * size
    return {
        "total": len(rows), "page": page, "pages": pages, "size": size,
        "items": [public_row(r) for r in rows[start:start + size]],
    }


CSV_COLUMNS = [
    "row", "student_name", "education", "domain_interest", "career_goal", "experience_level",
    "preferred_location", "preferred_duration_months", "status",
    "predicted_category", "model_confidence_pct", "match_score_pct", "top_skills", "missing_skills",
    "recommended_internships", "issues",
]


def _csv_cell(value):
    text = "" if value is None else str(value)
    if re.match(r"^[=+\-@]", text):
        text = "'" + text  # stop spreadsheet formulas running
    return '"' + text.replace('"', '""') + '"' if re.search(r'[",\r\n]', text) else text


def export_lines(job):
    """Yields the CSV report one line at a time, so large files stream without building in memory."""
    yield "﻿" + ",".join(CSV_COLUMNS) + "\r\n"
    for row in job["rows"]:
        d = public_row(row)
        values = [
            d["row"], d["student_name"], d["education"], d["domain_interest"], d["career_goal"],
            d["experience_level"], d["preferred_location"], d.get("preferred_duration_months", 6),
            d["status"], d["predicted_category"] or "", d["confidence"] or "",
            d["match_score"] if d["match_score"] is not None else "",
            " | ".join(d["skills"]), " | ".join(d["missing_skills"]),
            " | ".join(f"{r['title']} ({r['company']})" for r in d["recommended"]),
            "; ".join(d["errors"]),
        ]
        yield ",".join(_csv_cell(v) for v in values) + "\r\n"
