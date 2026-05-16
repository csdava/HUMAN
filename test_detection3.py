# -*- coding: utf-8 -*-
from ultralytics import YOLO
import json
import os

img_path = r"D:\User\Pictures\Saved Pictures\微信图片_20260515132613_298_18.jpg"
output_path = r"D:\User\Documents\PycharmProjects\human\detection_result.json"

results_data = {}

# Vegetable model
veg_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt')
veg_results = veg_model.predict(source=img_path, imgsz=640, conf=0.25, verbose=False)
veg_detections = []
if veg_results and len(veg_results) > 0:
    r = veg_results[0]
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            cls_id = int(box.cls.cpu().numpy()[0])
            conf = float(box.conf.cpu().numpy()[0])
            name = r.names[cls_id] if cls_id < len(r.names) else 'unknown'
            veg_detections.append({"name": name, "conf": conf})
results_data["vegetable"] = veg_detections

# Fruit model
fruit_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/fruit_train/weights/best.pt')
fruit_results = fruit_model.predict(source=img_path, imgsz=640, conf=0.25, verbose=False)
fruit_detections = []
if fruit_results and len(fruit_results) > 0:
    r = fruit_results[0]
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            cls_id = int(box.cls.cpu().numpy()[0])
            conf = float(box.conf.cpu().numpy()[0])
            name = r.names[cls_id] if cls_id < len(r.names) else 'unknown'
            fruit_detections.append({"name": name, "conf": conf})
results_data["fruit"] = fruit_detections

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results_data, f, ensure_ascii=False, indent=2)

print(f"Results saved to {output_path}")