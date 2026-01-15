"""
Debug script to check frame properties
"""
import cv2
import numpy as np

print("Opening camera...")
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

print("Camera opened successfully")
print("Reading 10 frames to check properties...")
print("=" * 60)

for i in range(10):
    ret, frame = cap.read()
    
    if not ret or frame is None:
        print(f"Frame {i+1}: FAILED to read")
        continue
    
    # Calculate properties
    mean_intensity = np.mean(frame)
    std_dev = np.std(frame)
    
    print(f"Frame {i+1}:")
    print(f"  Shape: {frame.shape}")
    print(f"  Mean intensity: {mean_intensity:.2f}")
    print(f"  Std deviation: {std_dev:.2f}")
    print(f"  Min value: {np.min(frame)}")
    print(f"  Max value: {np.max(frame)}")
    
    # Check validation
    valid = True
    if len(frame.shape) < 2 or frame.shape[0] < 50 or frame.shape[1] < 50:
        print(f"  ❌ INVALID: Frame too small")
        valid = False
    elif mean_intensity < 3:
        print(f"  ❌ INVALID: Too dark (mean < 3)")
        valid = False
    elif std_dev < 5:
        print(f"  ❌ INVALID: Too uniform (std < 5)")
        valid = False
    else:
        print(f"  ✓ VALID")
    
    print()

cap.release()
print("=" * 60)
print("Done!")
