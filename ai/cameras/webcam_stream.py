import cv2
from .base_stream import BaseCameraStream

class WebcamStream(BaseCameraStream):
    def __init__(self, camera_id=0 , zone=None):
        super().__init__(camera_id, zone)
        self.camera_id = camera_id
        self.cap = None
        self.zone = zone

    def start_stream(self):
        #Capturing from webcam
        self.cap = cv2.VideoCapture(self.camera_id)
        #Checking whether webcam is open or not
        if not self.cap.isOpened():
            raise RuntimeError("Could not open webcam")
        
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