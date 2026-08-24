import queue
import threading
import requests
import cv2
import numpy as np
from pathlib import Path
import traceback 
import time
import json # 🔴 اضافه شدن کتابخانه json برای پارس کردن ماسک

BASE_DIR = Path(__file__).resolve().parent.parent.parent

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QFrame, QLabel, QScrollArea, QCheckBox, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

# ایمپورت مستقیم و بدون دردسر ماژول‌های شما
from multi_camera_manager import MultiCameraManager
from cameras.webcam_stream import WebcamStream
from cameras.video_file_stream import VideoFileStream
from person_detector import YOLOv8PersonDetector
from face_recognition import ArcFaceRecognizer
from tracker import SimpleTracker
from attendance_logic import AttendanceLogic
from api_client import APIClient

from PIL import ImageFont, ImageDraw, Image
import arabic_reshaper
from bidi.algorithm import get_display

def put_persian_text(frame, text, position, color=(0, 255, 0), font_size=20):
    img_pil = Image.fromarray(frame)
    draw = ImageDraw.Draw(img_pil)
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    try:
        font = ImageFont.truetype("tahoma.ttf", font_size)
    except:
        font = ImageFont.load_default()
    draw.text(position, bidi_text, font=font, fill=color)
    np.copyto(frame, np.array(img_pil))
    return frame

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

class CentralAIEngineThread(QThread):
    frame_ready = pyqtSignal(str, QImage)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.cmd_queue = queue.Queue() 
        self.last_emit_time = {}
        # 🔴 کش کردن ماسک‌های نواحی مجاز کارگران برای کاهش درخواست‌های API
        self.employee_zones_cache = {} 

    def run(self):
        api_client = APIClient("http://localhost:8000")
        event_queue = queue.Queue()
        stop_event = threading.Event()
        
        sender_thread = threading.Thread(
            target=event_sender_worker, 
            args=(event_queue, api_client, stop_event), 
            daemon=True
        )
        sender_thread.start()

        manager = MultiCameraManager()
        detector = YOLOv8PersonDetector(conf_threshold=0.5)
        recognizer = ArcFaceRecognizer(api_client=api_client, device="cuda", similarity_threshold=0.45)
        tracker = SimpleTracker()
        attendance = AttendanceLogic(absent_timeout_seconds=10)

        manager.start_all()
        
        active_cameras = {}
        frame_counter = 0
        last_known_tracks = {}

        print("✅ [AI Thread] موتور هوش مصنوعی با موفقیت روشن شد و منتظر دوربین است...")

        while self._run_flag:
            try:
                while not self.cmd_queue.empty():
                    cmd = self.cmd_queue.get()
                    action = cmd["action"]
                    cam = cmd["cam"]
                    cam_id = str(cam["id"])
                    
                    if action == "add":
                        cam_type = cam["type"]
                        url = str(cam["rtsp_url"])
                        
                        if cam_type == "webcam":
                            stream = WebcamStream(int(url) if url.isdigit() else 0)
                        else:
                            full_path = BASE_DIR / url.lstrip("/\\")
                            stream = VideoFileStream(str(full_path))
                            
                        manager.add_camera(cam_id, stream)
                        active_cameras[cam_id] = True
                        last_known_tracks[cam_id] = []
                        
                        print(f"⏳ [AI Thread] در حال روشن کردن استریم دوربین {cam_id}...")
                        stream.start_stream()
                        print(f"✅ [AI Thread] دوربین {cam_id} روشن شد.")
                        
                    elif action == "remove":
                        if cam_id in active_cameras:
                            stream_obj = manager.cameras.get(cam_id) if hasattr(manager, 'cameras') else None
                            if stream_obj and hasattr(stream_obj, 'stop'):
                                stream_obj.stop()
                                
                        if hasattr(manager, 'remove_camera'):
                            manager.remove_camera(cam_id)
                        active_cameras.pop(cam_id, None)
                        last_known_tracks.pop(cam_id, None)
                        print(f"❌ [AI Thread] دوربین {cam_id} با موفقیت حذف شد.")

                if not active_cameras:
                    self.msleep(100)
                    continue

                frames = manager.get_frames()
                frame_counter += 1

                for cam_id, data in frames.items():
                    if cam_id not in active_cameras:
                        continue

                    raw_frame = data # 🔴 متغیر zone دوربین قدیمی دیگر نیاز نیست
                    
                    if raw_frame is None:
                        if frame_counter % 30 == 0:
                            print(f"⚠️ [AI Thread] هشدار: فریم جدیدی از دوربین {cam_id} دریافت نشد!")
                        continue

                    frame = raw_frame.copy()
                    h_frame, w_frame = frame.shape[:2]

                    if frame_counter % 3 == 0:
                        current_camera_tracks = []
                        detections = detector.detect(frame)
                        
                        for det in detections:
                            x1, y1, x2, y2 = map(int, det["bbox"])
                            result = recognizer.recognize(frame, [x1, y1, x2, y2], cam_id)

                            name = result.get("name", "unknown")
                            employee_id = result.get("employee_id")
                            
                            if employee_id is None:
                                employee_id = 0 
                            
                            raw_face_bbox = result.get("face_bbox")
                            if raw_face_bbox is None:
                                raw_face_bbox = [x1, y1, x2, y2]
                            fx1, fy1, fx2, fy2 = map(int, raw_face_bbox)

                            # 🔴 بررسی منطق گرید (Grid Zone) برای کارگر تشخیص داده شده
                            is_inside_grid = False
                            if employee_id > 0:
                                # واکشی از سرور در صورت عدم وجود در کش
                                if employee_id not in self.employee_zones_cache:
                                    self.employee_zones_cache[employee_id] = {}
                                    try:
                                        resp = requests.get(f"http://localhost:8000/employees/{employee_id}")
                                        if resp.status_code == 200:
                                            emp_data = resp.json()
                                            for shift in emp_data.get("shifts", []):
                                                s_cam_id = shift.get("camera_id")
                                                mask_str = shift.get("zone_mask")
                                                cells = set()
                                                if mask_str:
                                                    try:
                                                        cells = set(tuple(c) for c in json.loads(mask_str))
                                                    except: pass
                                                
                                                key = str(s_cam_id) if s_cam_id is not None else "all"
                                                self.employee_zones_cache[employee_id][key] = cells
                                    except Exception as e:
                                        print(f"Error fetching employee shifts: {e}")

                                # بررسی اینکه آیا مرکز باکس کارگر در منطقه مجاز اوست یا خیر
                                emp_cams = self.employee_zones_cache.get(employee_id, {})
                                allowed_cells = emp_cams.get(str(cam_id), emp_cams.get("all", set()))
                                
                                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                                grid_r, grid_c = int((cy / h_frame) * 16), int((cx / w_frame) * 16)
                                
                                if (grid_r, grid_c) in allowed_cells:
                                    is_inside_grid = True

                            # آپدیت ترکر (zone قدیمی را بی‌اثر می‌فرستیم)
                            track = tracker.update(
                                camera_id=cam_id, name=name, employee_id=employee_id, 
                                bbox=[x1, y1, x2, y2], inside_zone=is_inside_grid
                            )
                            
                            current_camera_tracks.append((track, [fx1, fy1, fx2, fy2]))
                        
                        last_known_tracks[cam_id] = current_camera_tracks
                    else:
                        current_camera_tracks = last_known_tracks.get(cam_id, [])

                    for track, face_bbox in current_camera_tracks:
                        label = f"T{track.track_id} {track.name}"
                        label += " IN" if track.inside_zone else " OUT"
                        color = (0, 255, 0) if track.name != "unknown" else (0, 0, 255)

                        fx1, fy1, fx2, fy2 = map(int, face_bbox)
                        cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), color, 2)

                        status_str = "داخل ناحیه مجاز" if track.inside_zone else "خارج از ناحیه"
                        display_text = f"{name} - {status_str}"

                        font_size = 30
                        if fy1 <= 0: 
                            fy1 = fy1 + 20 

                        frame = put_persian_text(frame, display_text, (fx1, fy1-70), color=color, font_size=font_size)

                    rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    resized = cv2.resize(rgb_image, (640, 480), interpolation=cv2.INTER_LINEAR)
                    resized = np.ascontiguousarray(resized)
                    h, w, ch = resized.shape
                    qt_img = QImage(resized.data, w, h, ch * w, QImage.Format_RGB888).copy()
                    now = time.time()
                    last = self.last_emit_time.get(cam_id, 0)
                    if now - last >= 0.033:  
                        self.last_emit_time[cam_id] = now
                        self.frame_ready.emit(cam_id, qt_img)

                events = attendance.process_tracks(tracker.tracks)
                for e in events:
                    event_queue.put(e)

                tracker.cleanup_tracks()
                self.msleep(33) 

            except Exception as ex:
                print(f"\n❌ [CRITICAL ERROR in AI Thread]: {ex}")
                traceback.print_exc()

        stop_event.set()
        sender_thread.join()
        manager.stop_all()

    def stop(self):
        self._run_flag = False
        self.wait()

class FetchCamerasThread(QThread):
    cameras_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            response = requests.get("http://localhost:8000/cameras/")
            response.raise_for_status()
            cameras = [cam for cam in response.json() if cam.get("is_active", True)]
            self.cameras_ready.emit(cameras)
        except Exception as e:
            self.error_occurred.emit(str(e))

class LiveDashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        self.camera_panel = QFrame()
        self.camera_panel.setObjectName("Card")
        self.camera_panel.setFixedWidth(250)
        camera_panel_layout = QVBoxLayout(self.camera_panel)
        
        title_label = QLabel("لیست دوربین‌های فعال")
        title_label.setObjectName("CardTitle")
        title_label.setAlignment(Qt.AlignCenter)
        camera_panel_layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        self.checkbox_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.checkbox_container)
        camera_panel_layout.addWidget(scroll_area)

        self.video_area = QFrame()
        self.video_area.setObjectName("Card")
        self.video_layout = QGridLayout(self.video_area)
        self.video_layout.setAlignment(Qt.AlignTop)

        main_layout.addWidget(self.camera_panel)
        main_layout.addWidget(self.video_area, stretch=1)

        self.active_labels = {}
        
        self.ai_engine = CentralAIEngineThread()
        self.ai_engine.frame_ready.connect(self.update_image,Qt.QueuedConnection)
        self.ai_engine.start()

        self.load_cameras()

    def showEvent(self, event):
        super().showEvent(event)
        for i in reversed(range(self.checkbox_layout.count())): 
            widget = self.checkbox_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
                
        self.load_cameras()

    def load_cameras(self):
        self.api_thread = FetchCamerasThread()
        self.api_thread.cameras_ready.connect(self.populate_checkboxes)
        self.api_thread.error_occurred.connect(self.show_error)
        self.api_thread.start()

    def populate_checkboxes(self, cameras):
        if not cameras:
            self.checkbox_layout.addWidget(QLabel("هیچ دوربین فعالی یافت نشد."))
            return

        for cam in cameras:
            cam_name = cam.get("name", f"Camera {cam['id']}")
            checkbox = QCheckBox(cam_name)
            checkbox.setStyleSheet("font-size: 14px; padding: 5px;")
            checkbox.toggled.connect(lambda checked, c=cam: self.toggle_camera(checked, c))
            self.checkbox_layout.addWidget(checkbox)

    def toggle_camera(self, is_checked, cam_dict):
        cam_id = str(cam_dict["id"])
        
        if is_checked:
            video_label = QLabel(f"در حال اتصال به {cam_dict['name']}...")
            video_label.setAlignment(Qt.AlignCenter)
            video_label.setStyleSheet("background-color: black; color: white; border-radius: 5px;")
            video_label.setMinimumSize(400, 300)
            self.active_labels[cam_id] = video_label
            self.ai_engine.cmd_queue.put({"action": "add", "cam": cam_dict})
        else:
            self.ai_engine.cmd_queue.put({"action": "remove", "cam": cam_dict})
            if cam_id in self.active_labels:
                widget_to_remove = self.active_labels.pop(cam_id)
                self.video_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

        self.rearrange_video_grid()

    def update_image(self, cam_id, qt_img):
        if cam_id in self.active_labels:
            label = self.active_labels[cam_id]
            label.setPixmap(QPixmap.fromImage(qt_img))

    def rearrange_video_grid(self):
        row, col = 0, 0
        for widget in self.active_labels.values():
            self.video_layout.addWidget(widget, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1

    def show_error(self, error_msg):
        QMessageBox.warning(self, "خطا", f"ارتباط با دیتابیس قطع است:\n{error_msg}")
        
    def closeEvent(self, event):
        self.ai_engine.stop()
        super().closeEvent(event)