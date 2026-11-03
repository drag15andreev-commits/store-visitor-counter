"""YOLO загружается только при первой обработке; экспорт работает без модели."""
import cv2
import numpy as np
from ultralytics import YOLO

class YoloDetector:
    def __init__(self, weights):
        self.model=YOLO(weights)

    def __call__(self, raw):
        image=cv2.imdecode(np.frombuffer(raw,np.uint8),cv2.IMREAD_COLOR)
        if image is None: raise ValueError('Некорректное изображение')
        result=self.model(image,conf=0.35,classes=[0],verbose=False)[0]
        count=len(result.boxes) if result.boxes is not None else 0
        # Английские подписи штатного OpenCV не требуют поддержки кириллицы.
        annotated=result.plot()
        cv2.putText(annotated,f'People: {count}',(20,35),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
        ok,encoded=cv2.imencode('.jpg',annotated)
        if not ok: raise ValueError('Ошибка сохранения изображения')
        return count,encoded.tobytes()
