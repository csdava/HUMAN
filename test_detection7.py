# -*- coding: utf-8 -*-
from ultralytics import YOLO
import json

img_path = r"D:\User\Pictures\Saved Pictures\生成西瓜洋葱照片.png"

# Get vegetable model class names
veg_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt')
print("Vegetable model classes:", list(veg_model.names.values()))

# Test with very low conf threshold
veg_results = veg_model.predict(source=img_path, imgsz=640, conf=0.1, verbose=False)
print(f"\nWith conf=0.1, detections: {len(veg_results[0].boxes) if veg_results and veg_results[0].boxes is not None else 0}")
if veg_results and veg_results[0].boxes is not None and len(veg_results[0].boxes) > 0:
    for box in veg_results[0].boxes:
        cls_id = int(box.cls.cpu().numpy()[0])
        conf = float(box.conf.cpu().numpy()[0])
        name = veg_results[0].names[cls_id]
        print(f"  {name} (conf: {conf:.3f})")