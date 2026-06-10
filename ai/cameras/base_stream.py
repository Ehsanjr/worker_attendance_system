import cv2
import time
from threading import Thread
from abc import ABC

class BaseCameraStream(ABC):
    def __init__(self, source, zone):
        self.source = source
        self.resize = (1280, 720) 
        self.zone = zone
        
        # بهینه‌سازی بسیار مهم برای وب‌کم‌ها در سیستم‌عامل ویندوز
        if isinstance(source, int):
            self.stream = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            self.stream = cv2.VideoCapture(source)
            
        self.stopped = False

        if not self.stream.isOpened():
            print(f"❌ [Error] Could not open video source: {source}")
            self.grabbed = False
            self.frame = None
        else:
            self.grabbed, self.frame = self.stream.read()
            if self.grabbed and self.resize is not None:
                self.frame = cv2.resize(self.frame, self.resize)

    def start_stream(self):
        self.stopped = False
        t = Thread(target=self.update_stream, daemon=True)
        t.start()
        return self

    def update_stream(self):
        is_video_file = isinstance(self.source, str) and not self.source.startswith(("rtsp", "http"))

        while not self.stopped:
            grabbed, frame = self.stream.read()
            
            if not grabbed:
                if is_video_file:
                    # ← restart ویدیو از اول
                    self.stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    print(f"⚠️ [Stream] قطع ارتباط دوربین: {self.source}")
                    self.stop_stream()
                    break

            if self.resize is not None:
                frame = cv2.resize(frame, self.resize)

            self.grabbed = grabbed
            self.frame = frame

            if is_video_file:
                time.sleep(0.033)

        self.stream.release()

    def read_stream(self):
        return self.frame, self.zone

    def stop_stream(self):
        self.stopped = True