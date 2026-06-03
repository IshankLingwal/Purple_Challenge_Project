from __future__ import annotations

from ultralytics import YOLO


class PersonDetector:
    def __init__(self, model_name: str = "yolov8n.pt", conf: float = 0.35, imgsz: int = 640):
        self.model = YOLO(model_name)
        self.conf = conf
        self.imgsz = imgsz

    def detect(self, frame):
        results = self.model.predict(frame, imgsz=self.imgsz, conf=self.conf, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                cls_id = int(box.cls[0])
                # COCO class 0 = person
                if cls_id != 0:
                    continue

                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                detections.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": float(box.conf[0]),
                        "label": "person",
                    }
                )

        return detections