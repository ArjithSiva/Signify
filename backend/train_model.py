"""
Signify - model training
--------------------------
Trains a RandomForest classifier on the flex-sensor dataset collected by
collect_data.py. Run this again any time you add more labeled data.

Usage:
    python train_model.py
"""

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

CSV_PATH = "gesture_data.csv"
MODEL_PATH = "signify_model.pkl"
COLUMNS = ["thumb", "index", "middle", "ring", "pinky", "label"]

df = pd.read_csv(CSV_PATH, header=None, names=COLUMNS)
df["label"] = df["label"].astype(str)  # keep labels like "0".."9" as strings, not floats

X = df[["thumb", "index", "middle", "ring", "pinky"]]
y = df["label"]

print(f"Loaded {len(df)} samples across {y.nunique()} classes: {sorted(y.unique())}")

stratify = y if y.value_counts().min() >= 2 else None
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=stratify
)

model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("\nClassification Report:\n", classification_report(y_test, y_pred))

joblib.dump(model, MODEL_PATH)
print(f"Model saved to {MODEL_PATH}")
