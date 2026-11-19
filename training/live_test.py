
from collections import deque
from pathlib import Path

import cv2
import joblib
import mediapipe as mp
import numpy as np

from collect import extract_features

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILE = ROOT / "models" / "asl_static.joblib"

if not MODEL_FILE.exists():
    raise FileNotFoundError(
        "Train the model before running live_test.py"
    )

model = joblib.load(MODEL_FILE)

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    raise RuntimeError("Cannot open webcam.")

recent_predictions = deque(maxlen=5)

with mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
) as hands:

    while True:
        success, frame = camera.read()

        if not success:
            break

        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        results = hands.process(rgb)

        status = "No hand detected"
        confidence_text = ""

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]

            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

            features = extract_features(hand)

            probabilities = model.predict_proba(
                np.array([features])
            )[0]

            best_index = np.argmax(probabilities)

            predicted_sign = model.classes_[best_index]

            confidence = probabilities[best_index]

            if confidence >= 0.80:
                recent_predictions.append(predicted_sign)
            else:
                recent_predictions.clear()

            if (
                len(recent_predictions) == 5
                and len(set(recent_predictions)) == 1
            ):
                status = f"Detected: {predicted_sign}"
                confidence_text = (
                    f"Model score: {confidence * 100:.1f}%"
                )
            else:
                status = "Sign not recognized"

        else:
            recent_predictions.clear()

        cv2.rectangle(
            frame,
            (10, 10),
            (460, 105),
            (30, 30, 30),
            -1
        )

        cv2.putText(
            frame,
            status,
            (25, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            confidence_text,
            (25, 85),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (120, 255, 160),
            2
        )

        cv2.imshow(
            "Svara Live Recognition",
            frame
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

camera.release()
cv2.destroyAllWindows()
