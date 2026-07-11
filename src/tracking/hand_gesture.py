"""MediaPipe hand gesture recognition for page-turn control."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shutil
import sys
import tempfile
import urllib.request

import cv2
import mediapipe as mp
import numpy as np


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/1/gesture_recognizer.task"
)
PALM_INDICES = (0, 5, 9, 13, 17)


@dataclass(frozen=True)
class HandGestureFrame:
    timestamp: float
    gesture: str = "None"
    confidence: float = 0.0
    palm_x: Optional[float] = None
    palm_y: Optional[float] = None
    handedness: str = ""
    hand_present: bool = False


class HandGestureTracker:
    def __init__(
        self,
        model_path: Optional[str] = None,
        min_confidence: float = 0.7,
        mirror: bool = True,
    ) -> None:
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.components.processors import ClassifierOptions

        model_file = self._ensure_ascii_path(self._resolve_model_path(model_path))
        options = vision.GestureRecognizerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(model_file)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            canned_gesture_classifier_options=ClassifierOptions(
                score_threshold=min_confidence
            ),
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        self._mirror = mirror
        self._last_timestamp_ms = -1

    def process(self, frame: np.ndarray, timestamp: float) -> HandGestureFrame:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = max(int(timestamp * 1000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self._recognizer.recognize_for_video(image, timestamp_ms)

        if not result.hand_landmarks:
            return HandGestureFrame(timestamp=timestamp)

        landmarks = result.hand_landmarks[0]
        palm_x = sum(landmarks[index].x for index in PALM_INDICES) / len(PALM_INDICES)
        palm_y = sum(landmarks[index].y for index in PALM_INDICES) / len(PALM_INDICES)
        if self._mirror:
            palm_x = 1.0 - palm_x

        gesture = "None"
        confidence = 0.0
        if result.gestures and result.gestures[0]:
            gesture = result.gestures[0][0].category_name or "None"
            confidence = float(result.gestures[0][0].score)

        handedness = ""
        if result.handedness and result.handedness[0]:
            handedness = result.handedness[0][0].category_name or ""

        return HandGestureFrame(
            timestamp=timestamp,
            gesture=gesture,
            confidence=confidence,
            palm_x=float(palm_x),
            palm_y=float(palm_y),
            handedness=handedness,
            hand_present=True,
        )

    def close(self) -> None:
        self._recognizer.close()

    @staticmethod
    def _resolve_model_path(model_path: Optional[str]) -> Path:
        if model_path:
            path = Path(model_path).expanduser()
        elif getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            path = Path(sys._MEIPASS) / "assets" / "models" / "gesture_recognizer.task"
        else:
            path = Path(__file__).resolve().parents[2] / "assets" / "models" / "gesture_recognizer.task"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MODEL_URL, path)
        return path

    @staticmethod
    def _ensure_ascii_path(model_file: Path) -> Path:
        try:
            str(model_file).encode("ascii")
            return model_file
        except UnicodeEncodeError:
            target = Path(tempfile.gettempdir()) / "HeadScroll" / "models" / model_file.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(model_file, target)
            return target
