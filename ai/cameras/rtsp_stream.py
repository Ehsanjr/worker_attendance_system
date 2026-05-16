import cv2
from .base_stream import BaseCameraStream


class RTSPStream(BaseCameraStream):

    def __init__(self, rtsp_url: str, zone=None):
        super().__init__(rtsp_url, zone)
        self.rtsp_url = rtsp_url
        self.cap = None
        self.zone = zone

    def start_stream(self):
        #Capturing from RTSP
        self.cap = cv2.VideoCapture(self.rtsp_url)

        if not self.cap.isOpened():
            raise RuntimeError("Could not connect to RTSP stream")

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
