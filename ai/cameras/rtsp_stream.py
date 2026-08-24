from .base_stream import BaseCameraStream

class RTSPStream(BaseCameraStream):
    def __init__(self, rtsp_url: str):
        super().__init__(rtsp_url)