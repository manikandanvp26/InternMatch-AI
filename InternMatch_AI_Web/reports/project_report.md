# InternMatch AI — Mini Project Report

## Abstract
InternMatch AI is a student-facing internship recommendation prototype. It uses a Decision Tree Classifier to predict an internship category from a student's education, interests, career goal, projects, certifications, experience and number of skills. A separate rule-based module ranks internship listings by skill overlap and identifies missing skills.

## 1. Introduction
Students may struggle to connect their current skills with internship requirements. This project demonstrates a transparent recommendation workflow using a simple classification model and explainable rules. It is a learning prototype, not a hiring or eligibility decision system.

## 2. Objectives
- Predict a suitable internship category from a student profile.
- Rank example listings by profile skill overlap.
- Identify missing skills for each recommended listing.
- Demonstrate model evaluation with standard classification metrics.
- Provide an accessible web UI using Streamlit.

## 3. Methodology
### Data
The labelled student profile dataset has 900 **synthetically generated** examples and six target categories. Rules were used to create demonstration labels, with limited noise. This supports repeatable code execution but can introduce bias and does not represent real student outcomes. Public internship listing examples are kept separately in `data/internships.csv`, with source URL and checked date.

### Algorithm
A single `DecisionTreeClassifier` is used with maximum depth 7, minimum leaf size 5 and balanced class weights. Categorical features are one-hot encoded; numeric counts pass through the preprocessing pipeline. A stratified 80/20 train/test split uses random seed 42.

### Ranking and skill-gap analysis
The matching module compares comma-separated required skills against the student's entered skills. Skill overlap contributes up to 75 points. A 25-point category bonus is added when a listing's category matches the predicted category. Skills absent from the profile are displayed as gaps. These are deterministic rules, not additional ML algorithms.

## 4. System Architecture
Student profile → preprocessing pipeline → Decision Tree category prediction → public listing filter → rule-based skill match score → ranked listings and skill-gap suggestions.

## 5. Evaluation
See `../results/metrics.json` and `../results/classification_report.txt` for the measured metrics generated from the fixed held-out test set. The values are computed from the included synthetic dataset and are not evidence of performance on real student outcomes.

### Metrics
- Accuracy: fraction of test examples whose predicted class equals the label.
- Macro precision: unweighted average of per-class precision.
- Macro recall: unweighted average of per-class recall.
- Macro F1: unweighted average of per-class F1-score.

## 6. Results and Discussion
The app produces a predicted category and a ranked list of matching listing examples. Each card contains a match score, location, work mode, source link and missing skills. The Decision Tree is interpretable and lightweight, while the rule-based matching logic is easy to explain to evaluators.

## 7. Limitations
- Student labels are synthetic, not expert-annotated real-world suitability outcomes.
- Public listing details can change or expire; links must be checked before applying.
- Skill matching uses simple string normalization and can miss synonyms.
- Model confidence is not the probability of getting selected.
- No live scraping, login, resume parsing or application submission is implemented.

## 8. Future Enhancements
- Build a licensed, current listing ingestion pipeline from employer APIs or permitted datasets.
- Collect expert-reviewed student-profile/internship-fit labels and test on unseen real examples.
- Add synonym-aware skills taxonomy and explainable recommendation reasons.
- Add user accounts, saved listings and optional resume parsing with consent.
- Track listing last-verified date and automatically flag stale listings.

## 9. Conclusion
InternMatch AI demonstrates how a Decision Tree classifier and transparent rule-based matching can be combined in a Streamlit application. It supports career exploration by suggesting internship categories and identifying skill gaps. Real-world usefulness must be validated with current listings and reliable labelled data before making stronger claims.
