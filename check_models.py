from ultralytics import YOLO

# Check vegetable model
veg_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train_v2/weights/best.pt')
print("=== Vegetable Model Classes ===")
print(veg_model.names)

# Check fruit model
fruit_model = YOLO('D:/User/Documents/PycharmProjects/human/runs/fruit_train/weights/best.pt')
print("\n=== Fruit Model Classes ===")
print(fruit_model.names)