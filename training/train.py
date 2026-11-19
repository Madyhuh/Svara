
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "asl_landmarks.csv"
MODEL_FILE = ROOT / "models" / "asl_static.joblib"


def main():
    if not DATA_FILE.exists():
        print("Collect training data first.")
        return

    data = pd.read_csv(DATA_FILE)

    feature_columns = [
        f"feature_{i}" for i in range(63)
    ]

    X = data[feature_columns]
    y = data["label"]
    groups = data["session"]

    if groups.nunique() < 4:
        print("Collect at least 4 separate sessions.")
        return

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.25,
        random_state=42
    )

    train_idx, test_idx = next(
        splitter.split(X, y, groups)
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]

    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    if set(y_train) != set(y_test):
        print("Every sign must appear in both splits.")
        print("Collect more balanced sessions.")
        return

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=20,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    print("Training Svara ASL model...")

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    accuracy = accuracy_score(
        y_test,
        predictions
    )

    print("\nAccuracy:", round(accuracy * 100, 2), "%")

    print("\nClassification Report:")
    print(classification_report(
        y_test,
        predictions,
        zero_division=0
    ))

    print("\nConfusion Matrix:")
    labels = sorted(y.unique())

    print("Class order:", labels)
    print(confusion_matrix(
        y_test,
        predictions,
        labels=labels
    ))

    MODEL_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    joblib.dump(model, MODEL_FILE)

    print("\nModel saved to:", MODEL_FILE)


if __name__ == "__main__":
    main()
