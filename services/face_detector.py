from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceBox:
    x: int
    y: int
    width: int
    height: int

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


class FaceDetector:
    def __init__(self) -> None:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._classifier = cv2.CascadeClassifier(cascade_path)
        if self._classifier.empty():
            raise RuntimeError("OpenCV face detector could not load its Haar cascade.")

    def detect(self, image_bytes: bytes) -> list[FaceBox]:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("The uploaded image is invalid or unsupported.")
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        grayscale = cv2.equalizeHist(grayscale)
        detected = self._classifier.detectMultiScale(
            grayscale,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )
        return [FaceBox(int(x), int(y), int(width), int(height)) for x, y, width, height in detected]


face_detector = FaceDetector()