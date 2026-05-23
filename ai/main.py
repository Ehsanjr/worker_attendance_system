import cv2
import time
import threading
import queue
from pathlib import Path 
from multi_camera_manager import MultiCameraManager
from cameras.webcam_stream import WebcamStream
from cameras.video_file_stream import VideoFileStream

from person_detector import YOLOv8PersonDetector
from face_recognition import ArcFaceRecognizer
from tracker import SimpleTracker
from attendance_logic import AttendanceLogic
from api_client import APIClient

#---------------------------------
#thread for async api post
#---------------------------------
def event_sender_worker(event_queue, api_client, stop_event):
    while not stop_event.is_set() or not event_queue.empty():
        try:
            e = event_queue.get(timeout=0.2)
            api_client.send_attendance_event(e)
            event_queue.task_done()
        except queue.Empty:
            continue
        except Exception as ex:
            print(f"[API ERROR] {ex}")


def main():

    # ----------------------------------
    # API
    # ----------------------------------
    BASE_DIR = Path(__file__).resolve().parent.parent 

    # ----------------------------------
    # BASE_DIR
    # ----------------------------------
    api_client = APIClient("http://localhost:8000")

    # ----------------------------------
    # start thread
    # ----------------------------------
    event_queue = queue.Queue()
    stop_event = threading.Event()
    sender_thread = threading.Thread(target=event_sender_worker, args=(event_queue, api_client, stop_event), daemon=True)
    sender_thread.start()


    # ----------------------------------
    # cameras
    # ----------------------------------
    manager = MultiCameraManager()

    cameras_list = api_client.get_cameras()
    
    for cam in cameras_list:
        if cam.get("is_active"):
            name = cam["name"]
            cam_type = cam["type"]
            url = cam["rtsp_url"]
            relative_path = cam['rtsp_url'] 
            full_path = BASE_DIR / relative_path
            # در دیتابیس "zones" ذخیره کردید، در مدل شما [x1, y1, x2, y2] است
            zone = tuple(cam.get("zones", [0, 0, 0, 0])) 

            if cam_type == "webcam":
                stream = WebcamStream(int(url) if url.isdigit() else 0, zone)
            else:
                # مسیر فایل را با ../ اصلاح می‌کنیم
                stream = VideoFileStream(str(full_path), zone)
                
            manager.add_camera(name, stream)
            print(f"Loaded camera: {name} with zone {zone}")

    # ----------------------------------
    # AI models
    # ----------------------------------
    detector = YOLOv8PersonDetector(conf_threshold=0.5)

    recognizer = ArcFaceRecognizer(
        api_client=api_client,
        device="cuda",
        similarity_threshold=0.45
    )

    tracker = SimpleTracker()

    attendance = AttendanceLogic(absent_timeout_seconds=10)

    manager.start_all()

    # ----------------------------------
    # main loop
    # ----------------------------------

    while True:

        frames = manager.get_frames()

        for cam_id, data in frames.items():

            frame, zone = data

            if frame is None:
                continue

            zx1, zy1, zx2, zy2 = zone
            cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), (100, 200, 100), 2)

            detections = detector.detect(frame)

            for det in detections:

                x1, y1, x2, y2 = det["bbox"]

                result = recognizer.recognize(
                    frame,
                    [x1, y1, x2, y2]
                )

                name = result["name"]
                employee_id = result["employee_id"]
                face_bbox = result.get("face_bbox", [x1, y1, x2, y2])

                track = tracker.update(
                    camera_id=cam_id,
                    name=name,
                    employee_id=employee_id,
                    bbox=[x1, y1, x2, y2],
                    zone=zone
                )

                label = f"T{track.track_id} {track.name}"

                if track.inside_zone:
                    label += " IN"
                else:
                    label += " OUT"

                is_known = track.name != "unknown"
                color = (0, 255, 0) if is_known else (0, 0, 255)

                fx1, fy1, fx2, fy2 = face_bbox

                cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), color, 2)

                cv2.putText(
                    frame,
                    label,
                    (fx1, fy1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    2
                )

            cv2.imshow(cam_id, frame)

        # ----------------------------------
        # attendance logic
        # ----------------------------------

        events = attendance.process_tracks(tracker.tracks)

        for e in events:
            print(e)
            event_queue.put(e)


        tracker.cleanup_tracks()

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        time.sleep(0.01)


    stop_event.set()
    sender_thread.join()
    manager.stop_all()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
