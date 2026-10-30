"""Train the InternMatch AI Decision Tree model on the bundled synthetic dataset."""
from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parent
df = pd.read_csv(ROOT / "data" / "student_training_data.csv")
features = ["education","domain_interest","career_goal","projects_count","certifications_count","experience_level","skills_count"]
X, y = df[features], df["internship_category"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
pre = ColumnTransformer([
    ("categorical", OneHotEncoder(handle_unknown="ignore"), ["education","domain_interest","career_goal","experience_level"]),
    ("numeric", "passthrough", ["projects_count","certifications_count","skills_count"])
])
model = Pipeline([
    ("preprocess", pre),
    ("classifier", DecisionTreeClassifier(max_depth=7, min_samples_leaf=5, class_weight="balanced", random_state=42))
])
model.fit(X_train, y_train)
pred = model.predict(X_test)
metrics = {
    "dataset_type": "synthetic educational data; not real student outcomes",
    "training_rows": int(len(X_train)), "test_rows": int(len(X_test)), "features": features,
    "target": "internship_category", "algorithm": "DecisionTreeClassifier",
    "accuracy": float(accuracy_score(y_test, pred)),
    "macro_precision": float(precision_score(y_test, pred, average="macro", zero_division=0)),
    "macro_recall": float(recall_score(y_test, pred, average="macro", zero_division=0)),
    "macro_f1": float(f1_score(y_test, pred, average="macro", zero_division=0)),
    "classification_report": classification_report(y_test, pred, output_dict=True, zero_division=0),
    "confusion_matrix": confusion_matrix(y_test, pred, labels=model.classes_).tolist(),
    "class_labels": model.classes_.tolist(), "random_seed": 42
}
(ROOT / "models").mkdir(exist_ok=True)
(ROOT / "results").mkdir(exist_ok=True)
joblib.dump({"model": model, "features": features, "classes": list(model.classes_)}, ROOT / "models" / "decision_tree_pipeline.joblib")
(ROOT / "results" / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
(ROOT / "results" / "classification_report.txt").write_text(classification_report(y_test, pred, zero_division=0), encoding="utf-8")
feature_names = model.named_steps["preprocess"].get_feature_names_out()
(ROOT / "results" / "decision_rules.txt").write_text(export_text(model.named_steps["classifier"], feature_names=list(feature_names)), encoding="utf-8")
print("Model trained and saved.")
print(f"Accuracy: {metrics['accuracy']:.3f}")
print(f"Macro precision: {metrics['macro_precision']:.3f}")
print(f"Macro recall: {metrics['macro_recall']:.3f}")
print(f"Macro F1: {metrics['macro_f1']:.3f}")
print("Saved model: models/decision_tree_pipeline.joblib")
