import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
ASL_MODEL_PATH = MODEL_DIR / "asl_static.joblib"


def extract_features_from_landmarks(landmarks: List[Dict[str, float]]) -> List[float]:
    """
    Extracts normalized 63-dimensional features identically to training/collect.py.
    Landmarks is a list of 21 objects with 'x', 'y', 'z' coordinates.
    Reference point: Wrist (point 0).
    Scale: Distance from wrist (0) to middle-finger knuckle (point 9).
    """
    if len(landmarks) != 21:
        raise ValueError(f"Expected 21 hand landmarks, received {len(landmarks)}")

    wrist = landmarks[0]
    coordinates = []

    for pt in landmarks:
        coordinates.extend([
            pt["x"] - wrist["x"],
            pt["y"] - wrist["y"],
            pt["z"] - wrist["z"]
        ])

    mcp = landmarks[9]
    scale = math.sqrt(
        (mcp["x"] - wrist["x"]) ** 2 +
        (mcp["y"] - wrist["y"]) ** 2
    )
    scale = max(scale, 0.000001)

    return [value / scale for value in coordinates]


class RecognitionAdapter:
    """
    Pluggable Recognition Adapter.
    Currently delegates to the students' trained ASL single-hand static model.
    Easily extensible for two-hand and multi-language classifiers (ISL, BSL).
    """
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._load_models()

    def _load_models(self):
        if ASL_MODEL_PATH.exists():
            try:
                self._models["ASL"] = joblib.load(ASL_MODEL_PATH)
            except Exception as e:
                print(f"[RecognitionAdapter] Error loading ASL model: {e}")
                self._models["ASL"] = None
        else:
            self._models["ASL"] = None

    def get_supported_languages(self) -> List[Dict[str, Any]]:
        return [
            {
                "code": "ASL",
                "name": "American Sign Language",
                "is_model_available": self._models.get("ASL") is not None,
                "supported_signs": list(self._models["ASL"].classes_) if self._models.get("ASL") else ["A", "B", "L"],
                "hands_required": 1,
                "description": "Active student-trained classifier for ASL letters A, B, and L."
            },
            {
                "code": "ISL",
                "name": "Indian Sign Language",
                "is_model_available": False,
                "supported_signs": [],
                "hands_required": 2,
                "description": "Two-hand model architecture ready. Model pending student training."
            },
            {
                "code": "BSL",
                "name": "British Sign Language",
                "is_model_available": False,
                "supported_signs": [],
                "hands_required": 2,
                "description": "Two-hand model architecture ready. Model pending student training."
            }
        ]

    def predict(self, language: str, hands_data: List[List[Dict[str, float]]]) -> Dict[str, Any]:
        """
        Receives language code and hands_data: a list of hand landmark lists (each 21 points).
        Returns strict format:
        {
            "language": str,
            "status": "no_hand" | "unrecognized" | "recognized" | "model_unavailable",
            "prediction": str or None,
            "confidence": float or None,
            "hands_detected": int
        }
        """
        language = (language or "ASL").upper()
        num_hands = len(hands_data) if hands_data else 0

        # Status 1: No hand detected
        if num_hands == 0:
            return {
                "language": language,
                "status": "no_hand",
                "prediction": None,
                "confidence": None,
                "hands_detected": 0
            }

        # Status 2: Model unavailable
        model = self._models.get(language)
        if model is None:
            return {
                "language": language,
                "status": "model_unavailable",
                "prediction": None,
                "confidence": None,
                "hands_detected": num_hands
            }

        # For the existing single-hand ASL model
        primary_hand = hands_data[0]
        try:
            features = extract_features_from_landmarks(primary_hand)
            features_arr = np.array([features])

            probabilities = model.predict_proba(features_arr)[0]
            best_idx = int(np.argmax(probabilities))
            confidence = float(probabilities[best_idx])
            predicted_label = str(model.classes_[best_idx])

            # Apply student thresholding (as in live_test.py: >= 0.80)
            if confidence >= 0.80:
                return {
                    "language": language,
                    "status": "recognized",
                    "prediction": predicted_label,
                    "confidence": round(confidence, 3),
                    "hands_detected": num_hands
                }
            else:
                return {
                    "language": language,
                    "status": "unrecognized",
                    "prediction": None,
                    "confidence": round(confidence, 3),
                    "hands_detected": num_hands
                }

        except Exception as e:
            print(f"[RecognitionAdapter] Inference error: {e}")
            return {
                "language": language,
                "status": "unrecognized",
                "prediction": None,
                "confidence": None,
                "hands_detected": num_hands
            }


adapter = RecognitionAdapter()
