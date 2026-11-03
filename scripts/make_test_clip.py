"""Build a repeatable test video for ``--camera`` from Ultralytics' bundled sample image.

The nearest person's top is recoloured green. The clip shows them in red for
2 s (no trigger), in green for 14 s (trigger and a visit), then an empty grey
frame for 8 s (visitor left). Video files are looped by the camera reader.

    python scripts/make_test_clip.py /tmp/green_visitor.avi
    python -m greeter --mock --scripted --camera /tmp/green_visitor.avi
"""

import argparse

import cv2
import numpy as np


def recolour_torso(image: np.ndarray, hue: int) -> np.ndarray:
    from ultralytics import YOLO

    result = YOLO("yolo26n-pose.pt")(image, classes=[0], verbose=False)[0]
    if result.boxes is None or len(result.boxes) == 0:
        raise SystemExit("no person found in the sample image")
    boxes = result.boxes.xyxy.cpu().numpy()
    i = int(np.argmax(boxes[:, 3] - boxes[:, 1]))  # tallest = nearest
    x1, y1, x2, y2 = boxes[i]
    kp = result.keypoints.xy.cpu().numpy()[i]
    top = int(min(kp[5, 1], kp[6, 1]))
    left, right = int(min(kp[5, 0], kp[6, 0])), int(max(kp[5, 0], kp[6, 0]))
    pad = int(0.15 * (right - left))
    mask = np.zeros(image.shape[:2], np.uint8)
    poly = np.array([[left, top], [right, top], [right + pad, int(y2)], [left - pad, int(y2)]], np.int32)
    cv2.fillPoly(mask, [poly], 255)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hsv[..., 0] = np.where(mask > 0, hue, hsv[..., 0])
    hsv[..., 1] = np.where(mask > 0, 200, hsv[..., 1])
    v = hsv[..., 2].astype(np.float32)
    hsv[..., 2] = np.where(mask > 0, np.clip(90 + 0.6 * v, 0, 255), v).astype(np.uint8)  # keep the shading
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out", help="output .avi path")
    p.add_argument("--fps", type=int, default=10)
    args = p.parse_args()

    from ultralytics.utils import ASSETS

    image = cv2.imread(str(ASSETS / "zidane.jpg"))
    image = cv2.resize(image, (640, 360))
    canvas = np.full((480, 640, 3), 110, np.uint8)
    green = canvas.copy()
    red = canvas.copy()
    green[120:480] = recolour_torso(image, 60)
    red[120:480] = recolour_torso(image, 0)
    writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"MJPG"), args.fps, (640, 480))
    for frame, seconds in ((red, 2), (green, 14), (canvas, 8)):
        for _ in range(seconds * args.fps):
            writer.write(frame)
    writer.release()
    print("wrote", args.out)


if __name__ == "__main__":
    main()
