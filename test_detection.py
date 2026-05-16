from ultralytics import YOLO
import os

img_path = input("请输入图片路径: ").strip().strip('"')

if not os.path.exists(img_path):
    print(f"文件不存在: {img_path}")
else:
    # Vegetable model
    veg_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/last.pt')
    veg_results = veg_model.predict(source=img_path, imgsz=640, conf=0.25, verbose=False)
    print("=== 蔬菜模型检测结果 ===")
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