import cv2
import numpy as np
from typing import List, Dict, Any
from ultralytics import YOLO
import torch


class BasePersonDetector:
    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        raise NotImplementedError


class YOLOv8PersonDetector(BasePersonDetector):

    def __init__(
        self,
        conf_threshold: float = 0.5
    ):
        if torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        self.model = YOLO("models/yolov8n.pt")
        self.model.to(self.device)

        self.conf_threshold = conf_threshold

        # COCO class id for person
        self.person_class_id = 0

        print(
            f"YOLOv8PersonDetector initialized | "
            f"conf={conf_threshold} | device={self.device}"
        )

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect only PERSON class and return full body bbox.

        Returns:
            [
                {
                    "bbox": (x1, y1, x2, y2),
                    "confidence": float
                }
            ]
        """

        results = self.model(
            frame,
            verbose=False,
            conf=self.conf_threshold,
            classes=[self.person_class_id]  # ✅ فقط انسان
        )

        detections = []

        for r in results:
            if r.boxes is None:
                continue

            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = float(box.conf[0])

                detections.append({
                    "bbox": (x1, y1, x2, y2),
                    "confidence": confidence
                })

        return detections
