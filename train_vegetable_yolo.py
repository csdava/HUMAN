"""
YOLO26n Vegetable Recognition Training - Continue from last checkpoint
Resume training to further improve accuracy
"""
from ultralytics import YOLO

def main():
    # Dataset path
    data_yaml = 'D:/User/Documents/PycharmProjects/human/11蔬菜数据集/data.yaml'

    # Initialize YOLO26n model from last checkpoint to continue training
    model = YOLO('D:/User/Documents/PycharmProjects/human/runs/vegetable_train/weights/last.pt')

    # Continue training for another 100 epochs
    results = model.train(
        data=data_yaml,
        epochs=100,              # Another 100 epochs
        imgsz=640,               # Image size
        batch=16,                # RTX 4060 8GB -> batch 16
        device=0,                # Use GPU 0
        workers=4,              # CPU workers
        cache=False,            # Disable caching to save memory
        amp=True,               # Mixed precision
        project='D:/User/Documents/PycharmProjects/human/runs',
        name='vegetable_train_v2',  # New training run
        exist_ok=True,
        pretrained=True,
        resume=True,             # Resume from the loaded model
        optimizer='AdamW',
        lr0=0.0001,             # Lower learning rate for fine-tuning
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        warmup_bias_lr=0.1,
        box=7.5,
        cls=0.5,
        dfl=1.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=5.0,             # Reduced augmentation for fine-tuning
        translate=0.1,
        scale=0.3,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        mosaic=0.5,              # Reduced augmentation
        mixup=0.05,             # Reduced mixup
        copy_paste=0.0,
        verbose=True,
        seed=0,
        plots=True,
        save=True,
        save_period=10,
    )

    print("\nContinued training complete!")
    print(f"Results saved to: {results.save_dir}")

if __name__ == '__main__':
    main()