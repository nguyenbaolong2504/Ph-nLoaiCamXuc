# Model assets

- `expression.onnx`: MobileFaceNet / Progressive Teacher, 7 labels, OpenCV Zoo; Apache-2.0. Original order: angry, disgust, fearful, happy, neutral, sad, surprised. The app maps fearful→fear and surprised→surprise.
- `face_detector.tflite`: Google MediaPipe BlazeFace short-range, float16 version 1; Apache-2.0. Source: https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector.
- `manifest.json`: pinned source URLs, SHA-256 and exact file sizes. Both supplied pretrained binaries are tracked in Git so clone/pull includes them. `scripts/download_models.py` verifies local files without a network request; it downloads only missing or damaged files. Run `npm run models` in backend to verify them separately from dependency setup.
- Preprocessing for supplied expression model: 4 MediaPipe landmarks (2 eyes, nose, mouth center) → least-squares 112px similarity alignment → RGB → [-1, 1]. This differs from upstream's five YuNet landmarks; measure performance on your own test images.
- Research TorchScript `.pt`: RGB 224px, ImageNet normalization. Runtime preprocessing matches `ai/common.py` normalization. FER cropped training images and MediaPipe-aligned deployment faces may differ: validate domain shift.

The pretrained model's published benchmark is not this project's measured result. No test accuracy is claimed until you run evaluation on the project's test set.

Never load third-party TorchScript or checkpoint files unless their source is trusted.
