"""
Quick test to check if camera is accessible
"""
import cv2
import sys

print("Testing camera access...")
print("=" * 50)

# Try to open camera with DirectShow
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("❌ ERROR: Cannot open camera!")
    print("Possible reasons:")
    print("  1. Camera is being used by another application")
    print("  2. Camera permissions not granted")
    print("  3. No camera connected")
    sys.exit(1)

print("✓ Camera opened successfully")

# Try to read a frame
ret, frame = cap.read()

if not ret or frame is None:
    print("❌ ERROR: Cannot read frame from camera!")
    cap.release()
    sys.exit(1)

print(f"✓ Frame captured successfully: {frame.shape}")
print(f"  Resolution: {frame.shape[1]}x{frame.shape[0]}")
print(f"  Channels: {frame.shape[2]}")

# Release camera
cap.release()
print("\n✓ Camera test passed! Camera is working properly.")
print("=" * 50)
