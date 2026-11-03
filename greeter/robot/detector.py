"""Ultralytics YOLO26n person detection + ByteTrack tracking."""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from greeter.vision import Detection

log = logging.getLogger(__name__)


class PersonDetector:
    """Wraps ``YOLO.track`` and returns :class:`greeter.vision.Detection` objects.

    The default ``yolo26n-pose.pt`` is the YOLO26n person detector with 17 body
    keypoints, which the facing check needs. ``yolo26n.pt`` (COCO detect) also
    works; then facing is unknown and only colour and size decide.

    The default tracker is BoT-SORT with ReID (``botsort_reid.yaml``): appearance
    features keep a visitor's ID through short occlusions. No face recognition.
    """

    def __init__(
        self,
        model: str = "yolo26n-pose.pt",
        imgsz: int = 640,
        conf: float = 0.4,
        device: Optional[str] = None,
        tracker: str = "botsort.yaml",
    ) -> None:
        from ultralytics import YOLO, settings

        settings.update({"sync": False})  # no usage analytics leave the robot
        self.model = YOLO(model)
        self.imgsz, self.conf, self.device, self.tracker = imgsz, conf, device, tracker
        log.info("loaded %s (task=%s)", model, getattr(self.model, "task", "?"))

    def detect(self, frame: np.ndarray) -> List[Detection]:
        result = self.model.track(
            frame,
            persist=True,
            classes=[0],  # person
            tracker=self.tracker,
            conf=self.conf,
            imgsz=self.imgsz,
            device=self.device,
            save=False,  # never write annotated frames to runs/
            verbose=False,
        )[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(xyxy)
        kxy = kconf = None
        if getattr(result, "keypoints", None) is not None and result.keypoints.conf is not None:
            kxy = result.keypoints.xy.cpu().numpy()
            kconf = result.keypoints.conf.cpu().numpy()
        out = []
        for i, box in enumerate(xyxy):
            out.append(
                Detection(
                    track_id=ids[i],
                    bbox=(float(box[0]), float(box[1]), float(box[2]), float(box[3])),
                    conf=float(confs[i]),
                    keypoints=kxy[i] if kxy is not None else None,
                    keypoint_conf=kconf[i] if kconf is not None else None,
                )
            )
        return out
