"""InternMatch AI - run the analysis in Thonny and see the charts.

One-time setup in Thonny:
    Tools > Manage packages... > install: pandas, scikit-learn, joblib, matplotlib, openpyxl

Keep this file in the same folder as engine.py, the models/ folder and the data/ folder.
Then open this file in Thonny and press F5 (Run).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator
except ImportError:
    raise SystemExit("matplotlib is missing. In Thonny: Tools > Manage packages > matplotlib")

import engine  # the same engine used by the web app


def choose_file():
    """Open a file picker. Falls back to the sample file if no window can open."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Choose a student data file",
            filetypes=[("Student data", "*.csv *.tsv *.txt *.xlsx *.xls *.json *.xml"), ("All files", "*.*")],
        )
        root.destroy()
        return path or None
    except Exception:
        return None


def print_table(students):
    print()
    print(f"{'Student':22} {'Category':20} {'Match':>7} {'Confidence':>11}  {'Status':12} Missing skills")
    print("-" * 110)
    for s in students:
        if s["status"] == "Needs fix":
            print(f"{s['student_name'][:22]:22} NEEDS FIX (row {s['row']}): {'; '.join(s['errors'])}")
            continue
        missing = ", ".join(s["missing_skills"]) or "None"
        print(f"{s['student_name'][:22]:22} {s['predicted_category'][:20]:20} "
              f"{s['match_score']:6.1f}% {s['confidence']:10.1f}%  {s['status']:12} {missing}")
    print()


def draw_charts(students, summary, title):
    ok = [s for s in students if s["status"] != "Needs fix"]
    if not ok:
        print("No student could be analysed, so there are no charts to draw.")
        return

    names = [s["student_name"] for s in ok]
    scores = [s["match_score"] for s in ok]
    confidence = [s["confidence"] for s in ok]
    colors = ["#0E8C8C" if sc >= 75 else "#3F8FD2" if sc >= 50 else "#F26B5B" for sc in scores]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"InternMatch AI: {len(ok)} students analysed ({title})", fontsize=15, fontweight="bold")

    # 1. How many students fall into each predicted category
    ax = axes[0, 0]
    cats = summary["categories"]
    bars = ax.bar([c for c, _ in cats], [n for _, n in cats], color="#0E8C8C")
    ax.bar_label(bars)
    ax.set_title("Predicted internship categories")
    ax.set_ylabel("Number of students")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.tick_params(axis="x", rotation=25)

    # 2. Best match score for each student
    ax = axes[0, 1]
    ax.barh(names[::-1], scores[::-1], color=colors[::-1])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Best match score (%)")
    ax.set_title("Match score per student")
    ax.legend(handles=[
        plt.Rectangle((0, 0), 1, 1, color="#0E8C8C", label="High (75+)"),
        plt.Rectangle((0, 0), 1, 1, color="#3F8FD2", label="Good (50-74)"),
        plt.Rectangle((0, 0), 1, 1, color="#F26B5B", label="Explore (<50)"),
    ], loc="lower right", fontsize=8)

    # 3. Skills most often missing from the recommended internships
    ax = axes[1, 0]
    gaps = summary["top_gaps"]
    if gaps:
        bars = ax.barh([g for g, _ in gaps][::-1], [n for _, n in gaps][::-1], color="#F26B5B")
        ax.bar_label(bars)
    else:
        ax.text(0.5, 0.5, "No skill gaps found", ha="center", va="center", transform=ax.transAxes)
    ax.set_title("Most common missing skills")
    ax.set_xlabel("Number of students")

    # 4. Model confidence against match score for each student
    ax = axes[1, 1]
    ax.scatter(confidence, scores, c=colors, s=90, edgecolors="white")
    for name, x, y in zip(names, confidence, scores):
        ax.annotate(name.split()[0], (x, y), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Model confidence (%)")
    ax.set_ylabel("Match score (%)")
    ax.set_title("Confidence vs match score")
    ax.grid(alpha=0.3)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = HERE / f"{Path(title).stem}_analysis.png"
    fig.savefig(out, dpi=120)
    print("Chart saved to:", out)
    plt.show()


def main():
    path = choose_file() or str(HERE / "static" / "sample_template.csv")
    print("Analysing:", path)
    try:
        with open(path, "rb") as f:
            data = f.read()
        df = engine.parse_upload(Path(path).name, data)
        result = engine.analyse(df)
    except ValueError as exc:
        print("Could not analyse this file:", exc)
        return

    summary = result["summary"]
    print_table(result["students"])
    print(f"Analysed {summary['analysed']} of {summary['total_rows']} students. "
          f"Needs fix: {summary['needs_fix']}.")
    draw_charts(result["students"], summary, Path(path).name)


if __name__ == "__main__":
    main()
