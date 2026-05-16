import cv2
from threading import Thread
from abc import ABC, abstractmethod
import time


class BaseCameraStream(ABC):
    def __init__(self, source, zone):
        super().__init__()
        self.source = source
        self.resize = (1280,720)  # مثلا (960, 540)
        self.stream = cv2.VideoCapture(source)
        self.zone = zone

        # Checking whether video source is open or not
        if not self.stream.isOpened():
            print(f"[Error] could not open video from {source} source.")

        # Variables for saving frame and status
        self.grabbed, self.frame = self.stream.read()

        if self.grabbed and self.resize is not None:
            self.frame = cv2.resize(self.frame, self.resize)

        self.stopped = False

    def start_stream(self):
        # Reading frames in different threads
        t = Thread(target=self.update_stream, args=())
        t.daemon = True
        t.start()
        return self

    def update_stream(self):
        # Reading new frames in loop
        while True:
            if self.stopped:
                self.stream.release()
                return

            # Reading next frame
            grabbed, frame = self.stream.read()

            # if video finished or source connection lost
            if not grabbed:
                self.stop_stream()
                return

            if self.resize is not None:
                frame = cv2.resize(frame, self.resize)

            self.grabbed = grabbed
            self.frame = frame

            time.sleep(0.01)

    def read_stream(self):
        # returning last frame
        return self.frame, self.zone

    def stop_stream(self):
        # Stopping source and release resources
        self.stopped = True
