# -*- coding: utf-8 -*-
from ultralytics import YOLO
import json

img_path = r"D:\User\Pictures\Saved Pictures\生成西瓜洋葱照片.png"

# Vegetable model with conf=0.25
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
            veg_detections.append({"name": name, "conf": round(conf, 3)})
results_data = {"vegetable_conf025": veg_detections}

with open(r"D:\User\Documents\PycharmProjects\human\detection_result4.json", 'w', encoding='utf-8') as f:
    json.dump(results_data, f, ensure_ascii=False, indent=2)
print("Done")