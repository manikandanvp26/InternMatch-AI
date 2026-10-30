# InternMatch AI (web version)

InternMatch AI supports both individual student analysis and bulk student-file analysis.
Enter one student's profile manually, or upload student data in CSV, TSV, TXT, Excel, JSON or XML format
(up to 200,000 rows and 150 MB). The app predicts an internship category, ranks available bundled listings,
identifies missing skills, and exports bulk results as CSV or an individual recommendation report as PDF.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 in your browser.

## Individual student analysis

1. Open **Student Profile** in the sidebar.
2. Enter education, domain interest, career goal, experience, projects, certifications, skills and location.
3. Select the maximum internship duration and choose **Analyse My Profile**.
4. Review the predicted category, model confidence, ranked listings and missing skills.
5. Choose **Download PDF report** to save a personal recommendation report.

## Bulk file analysis

1. Drag a file onto the upload box, or click **Browse Files**. Maximum size is 150 MB (about 200,000 rows).
2. The app opens **Results** with one row per student: predicted category, match score, skills,
   missing skills, recommended internships and status.
3. Rows marked **Needs fix** say what is wrong, for example an unrecognised education value.
   Correct those in your file and upload it again.
4. Click **Download Results (CSV)** to save the report.

Not sure about the format? Click **Download Sample Template** on the upload page.

Column names are matched loosely, so "Full Name", "Certification Count" and "Skills" all work.
Accepted values for education, domain, career goal and experience are listed under **About → Format guide**.

Values that differ slightly from the accepted list (for example "B.Sc IT" or "Full-time") are converted using
`data/value_map.json`. The Results page lists every conversion that was made. Edit that file to change how values are matched.
Values that aren't in the file, such as "Blockchain", are still flagged as **Needs fix**.

For a large file the results are kept in memory for the most recent upload only. Upload again if the results expire.

## Files

- `app.py`: Flask web server, individual profile API and PDF report route
- `engine.py`: reads files, cleans values, runs the Decision Tree model and ranks internships
- `templates/index.html`, `static/style.css`, `static/app.js`: the interface
- `static/sample_template.csv`: the downloadable sample
- `models/decision_tree_pipeline.joblib`: trained model (from `train_model.py`)
- `data/internships.csv`: internship listings used for matching
- `data/value_map.json`: converts common variants of values to the values the model knows
- `results/metrics.json`: evaluation shown on the Model Evaluation page

## Important

Model labels come from synthetic training data, so category predictions only demonstrate the pipeline.
Internship listings come from public pages and may be out of date. Always check the employer's official page.


## Notes on the recommendation logic

- The Decision Tree predicts the internship category from the model's trained profile features.
- The internship match score is a separate rule-based score based on skill overlap and category match.
- Preferred duration is a filter for internship listings; it is not an additional ML feature.
- The bundled labelled student training data is synthetic. Evaluation scores are educational demonstration metrics, not evidence of real-world hiring performance.
- Listings are examples with source links and checked-date metadata. Verify each listing on its source before applying.
