import threading
import time
from pathlib import Path
import cv2
import numpy as np
from .config import ROOT, settings

LABELS = ["angry","disgust","fear","happy","neutral","sad","surprise"]
VI = dict(zip(LABELS,["Tức giận","Ghê tởm","Sợ hãi","Vui vẻ","Trung tính","Buồn","Ngạc nhiên"]))

class InferenceEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.detector = None
        self.classifier = None
        self.model_id = None
        self.error = None
        self.kind = "opencv"

    def load(self, record):
        import mediapipe as mp
        with self.lock:
            if not self.detector:
                options = mp.tasks.vision.FaceDetectorOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT/"models/face_detector.tflite")),
                    min_detection_confidence=0.5)
                self.detector = mp.tasks.vision.FaceDetector.create_from_options(options)
            path = (ROOT/"models"/record["path"]).resolve()
            if not path.is_relative_to((ROOT/"models").resolve()) or not path.is_file():
                raise RuntimeError("Không tìm thấy file mô hình hợp lệ.")
            if record["engine"] == "opencv":
                candidate = cv2.dnn.readNetFromONNX(str(path))
                candidate.setInput(np.zeros((1,3,112,112),np.float32))
                out = candidate.forward()
                if out.size != 7:
                    raise RuntimeError("Model phải có đúng 7 đầu ra.")
            else:
                import torch
                candidate = torch.jit.load(str(path), map_location="cpu").eval()
                with torch.no_grad():
                    if candidate(torch.zeros(1,3,224,224)).numel() != 7:
                        raise RuntimeError("Model phải có đúng 7 đầu ra.")
            self.classifier, self.kind, self.model_id = candidate, record["engine"], record["id"]
            self.error = None

    def close(self):
        if self.detector:
            self.detector.close()

    def status(self):
        return {"ready":self.classifier is not None,"model_id":self.model_id,"error":self.error}

    @staticmethod
    def align(image, detection):
        h,w = image.shape[:2]
        points = detection.keypoints
        eyes = sorted([[points[i].x*w,points[i].y*h] for i in (0,1)], key=lambda p:p[0])
        source = np.float32(eyes + [[points[2].x*w,points[2].y*h],[points[3].x*w,points[3].y*h]])
        target = np.float32([[38.2946,51.6963],[73.5318,51.5014],[56.0252,71.7366],[56.1396,92.3348]])
        # Deterministic least-squares similarity transform, no random RANSAC fit.
        x,y = source.T
        a = np.zeros((8,4),np.float32)
        a[0::2] = np.stack([x,-y,np.ones(4),np.zeros(4)],1)
        a[1::2] = np.stack([y,x,np.zeros(4),np.ones(4)],1)
        s,r,tx,ty = np.linalg.lstsq(a,target.flatten(),rcond=None)[0]
        return cv2.warpAffine(image,np.float32([[s,-r,tx],[r,s,ty]]),(112,112))

    def analyze(self, image, threshold=None):
        import mediapipe as mp
        start = time.perf_counter()
        with self.lock:
            if self.classifier is None:
                raise RuntimeError("Mô hình chưa sẵn sàng. Chạy scripts/download_models.py rồi khởi động lại.")
            h,w = image.shape[:2]
            result = self.detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)))
            faces = []
            for index,detection in enumerate(result.detections[:10]):
                b = detection.bounding_box
                x,y = max(0,b.origin_x),max(0,b.origin_y)
                x2,y2 = min(w,b.origin_x+b.width),min(h,b.origin_y+b.height)
                if x2 <= x or y2 <= y:
                    continue
                crop = image[y:y2,x:x2]
                blur = float(cv2.Laplacian(cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY),cv2.CV_64F).var())
                quality = "LOW_QUALITY" if min(x2-x,y2-y) < 40 or blur < 12 else "OK"
                face = {"face_id":index+1,"box":[x,y,x2-x,y2-y],"quality":quality,"blur":round(blur,2),"expression":None,"score":None,"scores":{},"status":quality}
                if quality == "OK":
                    aligned = self.align(image,detection)
                    if self.kind == "opencv":
                        rgb = cv2.cvtColor(aligned,cv2.COLOR_BGR2RGB).astype(np.float32)/127.5-1
                        self.classifier.setInput(cv2.dnn.blobFromImage(rgb))
                        logits = self.classifier.forward().reshape(-1)
                    else:
                        import torch
                        rgb = cv2.cvtColor(cv2.resize(aligned,(224,224)),cv2.COLOR_BGR2RGB).astype(np.float32)/255
                        rgb = (rgb-np.array([.485,.456,.406]))/np.array([.229,.224,.225])
                        tensor = torch.from_numpy(rgb.transpose(2,0,1).astype(np.float32)).unsqueeze(0)
                        with torch.no_grad():
                            logits = self.classifier(tensor).numpy().reshape(-1)
                    probs = np.exp(logits-logits.max()); probs /= probs.sum()
                    order = np.argsort(probs)[::-1]
                    face.update(scores={k:round(float(v),6) for k,v in zip(LABELS,probs)},score=float(probs[order[0]]))
                    accepted = probs[order[0]] >= (threshold if threshold is not None else settings.confidence_threshold) and probs[order[0]]-probs[order[1]] >= settings.margin_threshold
                    face.update(expression=LABELS[order[0]] if accepted else None,status="OK" if accepted else "UNCERTAIN")
                faces.append(face)
            return {"faces":faces,"status":"NO_FACE" if not faces else "COMPLETED","width":w,"height":h,"model_id":self.model_id,"latency_ms":round((time.perf_counter()-start)*1000,1)}

def decode_image(content):
    from PIL import Image, ImageOps, UnidentifiedImageError
    import io
    try:
        with Image.open(io.BytesIO(content)) as source:
            if source.format not in ("JPEG","PNG","WEBP"):
                raise ValueError("Chỉ hỗ trợ ảnh JPG, PNG, WebP.")
            if source.width*source.height > 20_000_000:
                raise ValueError("Ảnh vượt quá 20 megapixel.")
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail((1600,1600))
            return cv2.cvtColor(np.asarray(source),cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Không đọc được ảnh hoặc file không phải ảnh hợp lệ.") from exc

engine = InferenceEngine()
