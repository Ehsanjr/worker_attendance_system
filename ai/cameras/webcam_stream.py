from .base_stream import BaseCameraStream

class WebcamStream(BaseCameraStream):
    def __init__(self, camera_id=0):
        super().__init__(camera_id)