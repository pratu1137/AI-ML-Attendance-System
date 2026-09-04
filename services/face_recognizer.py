from dataclasses import dataclass

import numpy as np

from extensions import db
from models import FaceEnrollment, Student
from services.face_encoder import FaceEncoder, FaceEncoding


@dataclass(frozen=True)
class RecognitionResult:
    recognized: bool
    distance: float | None
    student: Student | None = None


class FaceRecognizer:
    def __init__(self, threshold: float = 0.75) -> None:
        if threshold <= 0:
            raise ValueError("Recognition threshold must be positive.")
        self.threshold = threshold

    def recognize(self, encoding: FaceEncoding) -> RecognitionResult:
        enrollments = db.session.scalars(
            db.select(FaceEnrollment)
            .join(FaceEnrollment.student)
            .where(FaceEnrollment.is_active.is_(True), Student.is_active.is_(True))
        ).all()
        best_student = None
        best_distance = None
        for enrollment in enrollments:
            if enrollment.representation_version != FaceEncoder.version:
                continue
            stored = np.frombuffer(enrollment.representation, dtype=np.float32)
            if stored.shape != encoding.vector.shape or not np.all(np.isfinite(stored)):
                continue
            distance = float(np.linalg.norm(encoding.vector - stored))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_student = enrollment.student
        if best_student is None or best_distance is None or best_distance > self.threshold:
            return RecognitionResult(recognized=False, distance=best_distance)
        return RecognitionResult(recognized=True, distance=best_distance, student=best_student)


def build_recognizer(threshold: float) -> FaceRecognizer:
    return FaceRecognizer(threshold=threshold)