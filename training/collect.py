import argparse
import csv
import time
from pathlib import Path
import cv2
import mediapipe as mp

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "asl_landmarks.csv"

SIGNS = {
    ord("1"): "A",
    ord("2"): "B",
    ord("3"): "L",
}

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils


def extract_features(hand):
    points = hand.landmark

    # Wrist is our reference point.
    wrist = points[0]

    coordinates = []

    for point in points:
        coordinates.extend([
            point.x - wrist.x,
            point.y - wrist.y,
            point.z - wrist.z
        ])

    # Normalize using distance from wrist
    # to middle-finger knuckle.
    scale = (
        (points[9].x - wrist.x) ** 2
        + (points[9].y - wrist.y) ** 2
    ) ** 0.5

    scale = max(scale, 0.000001)

    return [value / scale for value in coordinates]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    args = parser.parse_args()

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    new_file = not DATA_FILE.exists()

    file = open(DATA_FILE, "a", newline="")
    writer = csv.writer(file)

    if new_file:
        writer.writerow(
            ["session", "label"]
            + [f"feature_{i}" for i in range(63)]
        )

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        file.close()
        raise RuntimeError("Cannot open webcam.")

    current_sign = None
    last_saved = 0
    counts = {"A": 0, "B": 0, "L": 0}

    with mp_hands.Hands(
        static_image_mode=False,
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
                frame, cv2.COLOR_BGR2RGB
            )

            results = hands.process(rgb)

            hand_found = bool(
                results.multi_hand_landmarks
            )

            if hand_found:
                hand = results.multi_hand_landmarks[0]

                mp_draw.draw_landmarks(
                    frame,
                    hand,
                    mp_hands.HAND_CONNECTIONS
                )

                if (
                    current_sign is not None
                    and time.time() - last_saved >= 0.2
                ):
                    features = extract_features(hand)

                    writer.writerow([
                        args.session,
                        current_sign,
                        *features
                    ])

                    file.flush()

                    counts[current_sign] += 1
                    last_saved = time.time()

            status = (
                "Hand detected"
                if hand_found
                else "No hand detected"
            )

            cv2.putText(
                frame,
                f"Status: {status}",
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.putText(
                frame,
                f"Recording: {current_sign or 'OFF'}",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"A:{counts['A']} B:{counts['B']} L:{counts['L']}",
                (20, 105),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                "1=A  2=B  3=L  0=Stop  Q=Quit",
                (20, 140),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.imshow("Svara Data Collection", frame)

            key = cv2.waitKey(1) & 0xFF

            if key in SIGNS:
                current_sign = SIGNS[key]
                last_saved = time.time()

            elif key == ord("0"):
                current_sign = None

            elif key == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()
    file.close()

    print("Saved examples:", counts)


if __name__ == "__main__":
    main()
