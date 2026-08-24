from .base_stream import BaseCameraStream

class VideoFileStream(BaseCameraStream):
    def __init__(self, video_path: str):
        super().__init__(video_path)