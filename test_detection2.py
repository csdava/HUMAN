# -*- coding: utf-8 -*-
from ultralytics import YOLO
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

img_path = r"D:\User\Pictures\Saved Pictures\微信图片_20260515132613_298_18.jpg"

# Vegetable model
print("=== 蔬菜模型检测结果 ===")
veg_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt')
veg_results = veg_model.predict(source=img_path, imgsz=640, conf=0.25, verbose=False)
if veg_results and len(veg_results) > 0:
    r = veg_results[0]
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            cls_id = int(box.cls.cpu().numpy()[0])
            conf = float(box.conf.cpu().numpy()[0])
            name = r.names[cls_id] if cls_id < len(r.names) else 'unknown'
            print(f"  {name} (conf: {conf:.3f})")
    else:
        print("  未检测到任何目标")
else:
    print("  无结果")

# Fruit model
print("\n=== 水果模型检测结果 ===")
fruit_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/fruit_train/weights/best.pt')
fruit_results = fruit_model.predict(source=img_path, imgsz=640, conf=0.25, verbose=False)
if fruit_results and len(fruit_results) > 0:
    r = fruit_results[0]
    if r.boxes is not None and len(r.boxes) > 0:
        for box in r.boxes:
            cls_id = int(box.cls.cpu().numpy()[0])
            conf = float(box.conf.cpu().numpy()[0])
            name = r.names[cls_id] if cls_id < len(r.names) else 'unknown'
            print(f"  {name} (conf: {conf:.3f})")
    else:
        print("  未检测到任何目标")
else:
    print("  无结果")