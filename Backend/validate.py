import cv2
from ultralytics import YOLO
from sklearn.model_selection import train_test_split
import numpy as np
import torch

# ----------------------------
# CONFIGURATION
# ----------------------------
model_path = "C:/Users/HP/OneDrive/Desktop/newproject/models/best.pt"  # your trained YOLO model
dataset_path = "C:/Users\HP/OneDrive/Desktop/pdemo/Dataset1-1"  # optional, only if you want split ratio
test_size = 0.2  # 80% train, 20% test
confidence_threshold = 0.4

# ----------------------------
# MODEL LOADING
# ----------------------------
model = YOLO(model_path)
print("\n✅ Model loaded successfully!")

# ----------------------------
# (OPTIONAL) DATASET SPLIT CHECK
# ----------------------------
try:
    import os
    all_images = [f for f in os.listdir(dataset_path) if f.endswith(('.jpg', '.png', '.jpeg'))]
    train_imgs, test_imgs = train_test_split(all_images, test_size=test_size, random_state=42)
    print(f"\n📊 Dataset Split:")
    print(f" - Total images: {len(all_images)}")
    print(f" - Train: {len(train_imgs)} ({(1-test_size)*100:.0f}%)")
    print(f" - Test: {len(test_imgs)} ({test_size*100:.0f}%)")
except Exception as e:
    print("\n⚠️ Dataset path not provided or invalid. Skipping split check.")

# ----------------------------
# VALIDATION (mAP / Accuracy)
# ----------------------------
print("\n🔍 Evaluating model on test data (if available)...")
try:
    metrics = model.val()  # evaluates on validation data (configured in YOLO training)
    print(f"\n📈 Model Validation Results:")
    print(f" - mAP50: {metrics.box.map50:.2f}")
    print(f" - mAP50-95: {metrics.box.map:.2f}")
    print(f" - Precision: {metrics.box.precision:.2f}")
    print(f" - Recall: {metrics.box.recall:.2f}")
except Exception as e:
    print("⚠️ Could not run validation. Ensure validation dataset is available.")

# ----------------------------
# LIVE CAMERA DETECTION
# ----------------------------
print("\n🎥 Starting live camera detection... Press 'q' to quit.")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Error: Could not access the webcam.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLO prediction
    results = model.predict(frame, conf=confidence_threshold, verbose=False)

    # Draw detections on frame
    annotated_frame = results[0].plot()

    # Display frame
    cv2.imshow("YOLO Live Validation", annotated_frame)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("\n✅ Live validation ended successfully.")
