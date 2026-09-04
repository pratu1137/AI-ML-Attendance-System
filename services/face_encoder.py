from dataclasses import dataclass

import cv2
import numpy as np

from services.face_detector import FaceBox


class FaceEncodingError(ValueError):
    pass


@dataclass(frozen=True)
class FaceEncoding:
    vector: np.ndarray
    version: str = "gray128-l2-v1"


class FaceEncoder:
    version = "gray128-l2-v1"

    def encode_sample(self, image_bytes: bytes, face: FaceBox) -> FaceEncoding:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FaceEncodingError("The uploaded image is invalid or unsupported.")
        crop = image[face.y:face.y + face.height, face.x:face.x + face.width]
        if crop.size == 0 or face.width < 60 or face.height < 60:
            raise FaceEncodingError("Face is too small for enrollment.")
        if float(np.mean(crop)) < 25 or float(np.mean(crop)) > 235:
            raise FaceEncodingError("Face lighting is too dark or too bright.")
        if float(cv2.Laplacian(crop, cv2.CV_64F).var()) < 20:
            raise FaceEncodingError("Face image is too blurry.")
        resized = cv2.resize(crop, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
        normalized = (resized - float(resized.mean())) / max(float(resized.std()), 1.0)
        vector = normalized.reshape(-1)
        vector /= max(float(np.linalg.norm(vector)), 1.0)
        return FaceEncoding(vector=vector.astype(np.float32))

    def aggregate(self, encodings: list[FaceEncoding]) -> FaceEncoding:
        if not encodings:
            raise FaceEncodingError("At least one face sample is required.")
        vector = np.mean([encoding.vector for encoding in encodings], axis=0).astype(np.float32)
        vector /= max(float(np.linalg.norm(vector)), 1.0)
        return FaceEncoding(vector=vector)

    @staticmethod
    def serialize(encoding: FaceEncoding) -> bytes:
        return encoding.vector.astype(np.float32).tobytes()


face_encoder = FaceEncoder()