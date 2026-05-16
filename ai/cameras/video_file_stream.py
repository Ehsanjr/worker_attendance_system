import cv2
from .base_stream import BaseCameraStream

class VideoFileStream(BaseCameraStream):
    def __init__(self, video_path:str , zone=None):
        super().__init__(video_path, zone)
        self.video_path = video_path
        self.cap = None
        self.zone = zone

    def start_stream(self):
        #Capturing from videofile
        self.cap = cv2.VideoCapture(self.video_path)

        if not self.cap.isOpened():
            raise RuntimeError("Could not open video file")

        super().start_stream()


    def _read_frame(self):
        #Reading from cap
        ret, frame = self.cap.read()

        if not ret:
            return None

        return frame
    
    def stop_stream(self):
        #Releasing camera when program stoped
        super().stop_stream()

        if self.cap is not None:
            self.cap.release()

