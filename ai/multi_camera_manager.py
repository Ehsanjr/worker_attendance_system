from typing import Dict
from threading import Lock


class MultiCameraManager:

    def __init__(self):
        self.cameras: Dict[str, object] = {}
        self.camera_status: Dict[str, bool] = {}
        self.lock = Lock()



    def add_camera(self, camera_id, stream):
        
        with self.lock:
            
            if camera_id in self.cameras:
                raise ValueError(f"Camera {camera_id} already exists.")
            
            self.cameras[camera_id] = stream

            self.camera_status[camera_id] = False

    


    def start_all(self):

        with self.lock:

            for camera_id, stream in self.cameras.items():

                try:
                    stream.start_stream()
                    self.camera_status[camera_id] = True
                    print(f"[INFO] Camera started: {camera_id}")

                except Exception as error:
                    self.camera_status[camera_id] = False
                    print(f"[ERROR] Failed to start {camera_id}: {error}")



    def get_frames(self):

        frames = {}

        with self.lock:
            for camera_id, stream in self.cameras.items():
                
                if stream.stopped:
                    self.camera_status[camera_id] = False
                    continue

                try:
                    frame, zone = stream.read_stream()

                    if frame is None:
                        self.camera_status[camera_id] = False
                        continue

                    frames[camera_id] = (frame, zone)
                    self.camera_status[camera_id] = True

                except Exception as error:
                    self.camera_status[camera_id] = False
                    print(f"[ERROR] Reading frame from {camera_id}: {error}")

        return frames
    

    def get_camera_status(self):

        with self.lock:
            return self.camera_status.copy()
        

    def remove_camera(self, camera_id):

        with self.lock:

            if camera_id not in self.cameras:
                return
            
            stream = self.cameras[camera_id]

            stream.stop_stream()

            del self.cameras[camera_id]

            del self.camera_status[camera_id]

            print(f"[INFO] Camera removed: {camera_id}")


    def stop_all(self):

        with self.lock:

            for camera_id, stream in self.cameras.items():
                
                try:
                    stream.stop_stream()
                    self.camera_status[camera_id] = False
                    print(f"[INFO] Camera stopped: {camera_id}")

                except Exception as error:
                    print(f"[ERROR] Stopping {camera_id}: {error}")

