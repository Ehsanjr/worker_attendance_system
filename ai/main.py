import cv2
import time

from multi_camera_manager import MultiCameraManager
from cameras.webcam_stream import WebcamStream
from cameras.video_file_stream import VideoFileStream
from person_detector import YOLOv8PersonDetector
from face_recognition import ArcFaceRecognizer
from tracker import SimpleTracker
from attendance_logic import AttendanceLogic


def main():

    manager = MultiCameraManager()

    # cameras
    #manager.add_camera("webcam", WebcamStream(0, (500, 200, 1000, 600)))
    #manager.add_camera("video1", VideoFileStream("../data/videos/1.mp4", (300,200,900,700)))
    #manager.add_camera("video2", VideoFileStream("../data/videos/2.mp4", (450,200,750,600)))
    manager.add_camera("video3", VideoFileStream("../data/videos/3.mp4", (450,200,750,600)))

    detector = YOLOv8PersonDetector(conf_threshold=0.5)
    recognizer = ArcFaceRecognizer("../data/workers", "cuda", 0.45)

    tracker = SimpleTracker()
    attendance = AttendanceLogic(absent_timeout_seconds=10)

    manager.start_all()

    while True:

        frames = manager.get_frames()

        for cam_id, data in frames.items():

            frame, zone = data

            if frame is None:
                continue

            # draw zone
            zx1, zy1, zx2, zy2 = zone
            cv2.rectangle(frame, (zx1, zy1), (zx2, zy2), (100, 200, 100), 2)

            # detection
            detections = detector.detect(frame)

            for det in detections:

                x1, y1, x2, y2 = det["bbox"]

                result = recognizer.recognize(frame, [x1, y1, x2, y2])

                recognized_name = result["name"]
                face_bbox = result["face_bbox"]

                track = tracker.update(
                    camera_id=cam_id,
                    name=recognized_name,
                    bbox=[x1, y1, x2, y2],
                    zone=zone
                )

                label = f"ID:{track.track_id} {track.name}"

                if track.inside_zone:
                    label += " IN"
                else:
                    label += " OUT"

                is_known = track.name != "unknown"
                color = (0, 255, 0) if is_known else (0, 0, 255)

                # face bbox
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

            # show frame
            cv2.imshow(cam_id, frame)

        # attendance logic (هر فریم یکبار)
        events = attendance.process_tracks(tracker.tracks)

        for e in events:
            print(e)

        # حذف track های خیلی قدیمی
        tracker.cleanup_tracks()

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        time.sleep(0.01)

    manager.stop_all()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
