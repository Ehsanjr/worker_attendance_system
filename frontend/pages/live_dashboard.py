import queue
import threading
import requests
import cv2
import numpy as np
from pathlib import Path
import traceback 
import time
import json # 🔴 اضافه شدن کتابخانه json برای پارس کردن ماسک
from concurrent.futures import ThreadPoolExecutor, as_completed  # 🔴 برای موازی‌سازیِ چهره‌یابیِ چند دوربین

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

def match_face_to_body(face_bbox, body_bboxes, used_bodies):
    """
    🔴 چون حالا چهره‌یابی مستقیم روی کل فریم انجام می‌شود (نه داخل کراپِ هر بدن)،
    باید مشخص کنیم هر چهره‌ی پیدا‌شده متعلق به کدام باکسِ بدنِ YOLO است.

    نکته‌ی مهم: وقتی دو نفر نزدیک هم می‌ایستند، باکس‌های بدنشان هم‌پوشانی دارند،
    پس مرکزِ چهره‌ی یک نفر می‌تواند هم‌زمان داخل باکسِ خودش هم داخل باکسِ نفرِ
    کناری بیفتد. به همین دلیل «اولین باکسی که چهره داخلش است» کافی نیست و باید
    از بین همه‌ی باکس‌های کاندید، آن‌که واقعاً «صاحبِ» این چهره است انتخاب شود:
    صورتِ خودِ فرد معمولاً نزدیکِ مرکزِ افقیِ باکسِ بدنِ خودش است (نه لبه‌ها) و
    در بخشِ بالاییِ باکس قرار دارد (سر همیشه بالای بدن است).
    """
    fx1, fy1, fx2, fy2 = face_bbox
    fcx, fcy = (fx1 + fx2) / 2, (fy1 + fy2) / 2

    best_idx, best_score = None, -1.0
    for idx, (bx1, by1, bx2, by2) in enumerate(body_bboxes):
        if idx in used_bodies:
            continue

        bw, bh = bx2 - bx1, by2 - by1
        if bw <= 0 or bh <= 0:
            continue

        # کمی حاشیه‌ی تحمل خارج از باکس هم قبول می‌شود (خطای جزئیِ باکس‌بندی YOLO)
        margin_x, margin_y = bw * 0.15, bh * 0.15
        if not (bx1 - margin_x <= fcx <= bx2 + margin_x and by1 - margin_y <= fcy <= by2 + margin_y):
            continue

        # امتیاز مرکزیتِ افقی: ۱ یعنی دقیقاً وسط باکس، هرچه به لبه نزدیک‌تر امتیاز کمتر
        h_offset = abs(fcx - (bx1 + bx2) / 2) / (bw / 2 + 1e-6)
        h_score = max(0.0, 1.0 - h_offset)

        # امتیاز موقعیتِ عمودی: انتظار داریم چهره در حدود ۱۵٪ بالای باکس باشد
        v_rel = (fcy - by1) / bh
        v_score = max(0.0, 1.0 - abs(v_rel - 0.15) / 0.5)

        score = h_score * 0.6 + v_score * 0.4
        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx

def build_camera_roster(cam_id, recognizer, tracker):
    """
    🔴 لیست کارگرانی که طبق دیتابیس الان شیفتشون جلوی این دوربینه، به‌همراه
    وضعیت لحظه‌ایشون (داخل ناحیه / خارج ناحیه ولی هنوز غایب نشده / غایب)،
    به‌علاوه‌ی کارگرانی که در فریم شناسایی شدن ولی الان شیفتشون نیست (نارنجی).
    """
    roster = []
    scheduled_ids = set()

    # 1) کارگرانی که الان طبق شیفتشون باید جلوی این دوربین باشند
    for emp_id, data in recognizer.known_embeddings.items():
        if not recognizer._is_allowed(data, cam_id):
            continue
        scheduled_ids.add(emp_id)

        track = next(
            (tr for tr in tracker.tracks.values()
             if tr.camera_id == cam_id and tr.employee_id == emp_id),
            None
        )

        if track is None:
            status, color = "absent", "#e53935"        # قرمز: اصلا دیده نشده
        elif track.inside_zone:
            status, color = "inside", "#43a047"         # سبز: حاضر و داخل ناحیه
        elif track.absent_sent:
            status, color = "absent", "#e53935"         # قرمز: به ترشولد غیبت رسیده
        else:
            status, color = "outside", "#43a047"        # سبز: خارج ناحیه ولی هنوز به ترشولد غیبت نرسیده

        roster.append({"name": data.get("name", "?"), "status": status, "color": color})

    # 2) کارگرانی که در فریم شناسایی شدند ولی الان شیفتشون نیست (نارنجی)
    for tr in tracker.tracks.values():
        if tr.camera_id != cam_id:
            continue
        if tr.employee_id and tr.employee_id > 0 and tr.employee_id not in scheduled_ids:
            roster.append({"name": tr.name, "status": "off_shift", "color": "#fb8c00"})

    return roster


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
    roster_ready = pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self._run_flag = True
        self.cmd_queue = queue.Queue() 
        self.last_emit_time = {}
        self.last_roster_emit_time = {}
        self.employee_zones_cache = {} 

    def stop(self):
        """
        🔴 قبلاً این متد اصلاً وجود نداشت ولی closeEvent صداش می‌زد -> AttributeError
        هنگامِ بستنِ صفحه. پرچمِ اجرا را خاموش می‌کند تا حلقه‌ی run() در اولین
        فرصت (حداکثر یک msleep) خارج شود، و بعد صبر می‌کند تا Thread واقعاً تمام
        شود (که در انتهای run() دوربین‌ها را هم متوقف می‌کند) — نه اینکه پنجره
        فوراً بسته شود درحالی‌که Threadِ AI هنوز در حالِ کار کردن روی دوربین‌هاست.
        """
        self._run_flag = False
        self.wait(3000)

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
                    if action == "reload_faces":
                        print("⏳ [AI Thread] در حال دریافت مجدد چهره‌ها از دیتابیس...")
                        recognizer.load_workers()
                        # پاک کردن کش نواحی تا مناطق کارگر جدید هم خوانده شود
                        self.employee_zones_cache.clear() 
                        print("✅ [AI Thread] چهره‌های جدید با موفقیت به کارت گرافیک منتقل شدند.")
                        continue # رفتن به دستور بعدی
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

                # 🔴 فازِ ۱ (batch): جمع‌آوریِ فریمِ دوربین‌های فعال، سپس یک عبورِ
                # واحدِ YOLO برای همه‌شون با هم + چهره‌یابیِ هر دوربین به‌صورتِ
                # موازی با ThreadPool — به‌جای پردازشِ کاملاً سری‌وار قبلی که با
                # چند دوربینِ پرتراکم می‌توانست فاصله‌ی واقعیِ بینِ فریم‌های
                # پردازش‌شده را زیاد کند و خودِ دقتِ ترکینگ را پایین بیاورد.
                frame_copies = {}
                for cam_id, data in frames.items():
                    if cam_id not in active_cameras:
                        continue
                    if data is None:
                        if frame_counter % 30 == 0:
                            print(f"⚠️ [AI Thread] هشدار: فریم جدیدی از دوربین {cam_id} دریافت نشد!")
                        continue
                    frame_copies[cam_id] = data.copy()

                do_detect = (frame_counter % 3 == 0) and bool(frame_copies)
                detections_by_cam = {}
                face_results_by_cam = {}

                if do_detect:
                    cam_ids_list = list(frame_copies.keys())
                    frame_list = [frame_copies[cid] for cid in cam_ids_list]

                    try:
                        batched_detections = detector.detect_batch(frame_list)
                    except Exception as e:
                        print(f"[ERROR] batched YOLO detection failed: {e}")
                        batched_detections = [[] for _ in cam_ids_list]

                    detections_by_cam = {
                        cid: batched_detections[i] for i, cid in enumerate(cam_ids_list)
                    }

                    # چهره‌یابی برای هر دوربین کاملاً مستقل است؛ اجرای موازی با
                    # ThreadPoolExecutor (فراخوانی‌های onnxruntime/insightface هنگامِ
                    # محاسبه‌ی سنگین، GIL پایتون را آزاد می‌کنند، پس این موازی‌سازی
                    # واقعاً هم‌پوشانیِ زمانی ایجاد می‌کند، نه فقط ظاهریِ کد)
                    max_workers = min(4, len(cam_ids_list)) or 1
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        future_to_cam = {
                            executor.submit(recognizer.detect_and_recognize, frame_copies[cid], cid): cid
                            for cid in cam_ids_list
                        }
                        for future in as_completed(future_to_cam):
                            cid = future_to_cam[future]
                            try:
                                face_results_by_cam[cid] = future.result()
                            except Exception as e:
                                print(f"[ERROR] face recognition failed for camera {cid}: {e}")
                                face_results_by_cam[cid] = []

                # 🔴 فازِ ۲: به‌ازای هر دوربین، تطبیقِ بدن↔چهره، به‌روزرسانیِ ترک‌ها و رسم
                for cam_id, frame in frame_copies.items():
                    h_frame, w_frame = frame.shape[:2]

                    if do_detect and cam_id in detections_by_cam:
                        current_camera_tracks = []
                        detections = detections_by_cam[cam_id]
                        body_bboxes = [tuple(map(int, det["bbox"])) for det in detections]

                        # 🔴 ریفکتور: چهره‌یابی یک‌بار روی کل فریم (نه کراپ از باکس هر بدن)
                        face_results = face_results_by_cam.get(cam_id, [])

                        # اتصال هر چهره‌ی پیدا‌شده به باکسِ بدنِ YOLOِ متناظرش؛ چهره‌های
                        # با اطمینان بالاتر اول جفت می‌شوند تا در تداخل احتمالی برنده باشند
                        used_bodies = set()
                        matched_body_for_face = {}
                        for f_idx, fres in sorted(enumerate(face_results), key=lambda t: -t[1]["confidence"]):
                            b_idx = match_face_to_body(fres["face_bbox"], body_bboxes, used_bodies)
                            if b_idx is not None:
                                matched_body_for_face[b_idx] = f_idx
                                used_bodies.add(b_idx)

                        # 🔴 قدمِ پیش‌بینیِ کالمن: قبل از تطبیق، موقعیتِ همه‌ی ترک‌های
                        # این دوربین بر اساسِ سرعتِ تخمینی‌شان یک گام جلو برده می‌شود
                        tracker.predict_camera_tracks(cam_id)

                        # 🔴 تطبیقِ سراسری بین باکس‌های بدنِ این فریم و ترک‌های موجود
                        # (به‌جای تطبیقِ یکی‌یکی به ترتیبِ دلخواهِ YOLO که می‌توانست
                        # وقتی دو نفر نزدیک هم‌اند هویتشان را بین دو ترک جابه‌جا کند)
                        body_track_matches = tracker.match_bodies_to_tracks(
                            cam_id, [list(b) for b in body_bboxes]
                        )

                        for b_idx, (x1, y1, x2, y2) in enumerate(body_bboxes):
                            f_idx = matched_body_for_face.get(b_idx)
                            if f_idx is not None:
                                result = face_results[f_idx]
                            else:
                                # هیچ چهره‌ای برای این بدن در این فریم پیدا نشد (مثلاً صورت برگشته)
                                result = {"name": "unknown", "employee_id": None, "confidence": 0,
                                          "face_bbox": None, "shift_ok": False}

                            det_name = result.get("name", "unknown")
                            det_employee_id = result.get("employee_id") or 0

                            raw_face_bbox = result.get("face_bbox")
                            if raw_face_bbox is None:
                                raw_face_bbox = [x1, y1, x2, y2]
                            fx1, fy1, fx2, fy2 = map(int, raw_face_bbox)

                            # 🔴 این فریم ممکن است چهره دیده نشده باشد (مثلاً صورت برگشته)؛
                            # قبل از این‌که هویت این فریم را قطعی بدانیم، ببینیم آیا این باکس
                            # به یک ترکِ از قبل شناخته‌شده می‌خورد یا نه، تا اگر همین الان چهره
                            # ندیدیم، هویتِ ماندگارش را از دست ندهیم (وگرنه رنگ اشتباهی نارنجی می‌شود)
                            pre_track = body_track_matches.get(b_idx)
                            if det_employee_id > 0:
                                effective_employee_id = det_employee_id
                            elif pre_track is not None and pre_track.employee_id:
                                effective_employee_id = pre_track.employee_id
                            else:
                                effective_employee_id = 0

                            # آیا این کارگر (در صورت شناخته‌شدن) در شیفت/دوربین فعلی مجاز است؟
                            # بر اساس هویتِ واقعی محاسبه می‌شود، نه صرفاً نتیجه‌ی لحظه‌ایِ همین فریم
                            if effective_employee_id > 0:
                                emp_data = recognizer.known_embeddings.get(effective_employee_id)
                                shift_ok = recognizer._is_allowed(emp_data, cam_id) if emp_data else False
                            else:
                                shift_ok = False

                            is_inside_grid = False
                            if effective_employee_id > 0:
                                # 🔴 قبلاً اینجا یک درخواست HTTP سینکرون به بک‌اند زده می‌شد که
                                # کاملاً زائد بود: همین داده (shifts + zone_mask) از قبل در
                                # recognizer.known_embeddings موجود است (در load_workers/reload_faces
                                # خوانده شده)، پس فقط از حافظه ساخته می‌شود، بدون I/O شبکه‌ای وسطِ حلقه.
                                if effective_employee_id not in self.employee_zones_cache:
                                    zones_by_key = {}
                                    emp_data = recognizer.known_embeddings.get(effective_employee_id, {})
                                    for shift in emp_data.get("shifts", []):
                                        s_cam_id = shift.get("camera_id")
                                        mask_str = shift.get("zone_mask")
                                        cells = set()
                                        if mask_str:
                                            try:
                                                cells = set(tuple(c) for c in json.loads(mask_str))
                                            except: pass

                                        key = str(s_cam_id) if s_cam_id is not None else "all"
                                        zones_by_key[key] = cells
                                    self.employee_zones_cache[effective_employee_id] = zones_by_key

                                emp_cams = self.employee_zones_cache.get(effective_employee_id, {})
                                allowed_cells = emp_cams.get(str(cam_id), emp_cams.get("all", set()))

                                # 🔴 برای نگاشتِ درست به گرید زمین، محلِ ایستادنِ فرد باید از
                                # پایینِ باکس (نزدیکِ پا) گرفته شود، نه وسطِ باکس؛ چون ارتفاعِ
                                # باکسِ بدن بسته به فاصله از دوربین و میزانِ پیدا بودنِ بدن
                                # متغیر است، ولی پاها همیشه رویِ زمین‌اند.
                                foot_x = (x1 + x2) / 2
                                foot_y = y2
                                grid_r = min(15, max(0, int((foot_y / h_frame) * 16)))
                                grid_c = min(15, max(0, int((foot_x / w_frame) * 16)))
                                
                                if (grid_r, grid_c) in allowed_cells:
                                    is_inside_grid = True

                            track = tracker.update_matched(
                                pre_track, camera_id=cam_id, name=det_name, employee_id=det_employee_id,
                                confidence=result.get("confidence", 0.0), bbox=[x1, y1, x2, y2],
                                inside_zone=is_inside_grid
                            )
                            
                            current_camera_tracks.append((track, [fx1, fy1, fx2, fy2], shift_ok))
                        
                        last_known_tracks[cam_id] = current_camera_tracks
                    else:
                        current_camera_tracks = last_known_tracks.get(cam_id, [])

                    # 🔴 رسم دقیق اطلاعات اختصاصی هر ترک بدون نشت متغیر
                    for track, face_bbox, shift_ok in current_camera_tracks:
                        # بررسی شناسا بودن فرد (مستقل از حروف بزرگ/کوچک)
                        is_known = bool(track.name and track.name.strip().lower() != "unknown")

                        if not is_known:
                            # قرمز: چهره اصلاً شناسایی نشد
                            color = (0, 0, 255)
                            display_text = "ناشناس"
                        elif not shift_ok:
                            # نارنجی: شناخته شد، اما الان خارج از شیفت/دوربین مجازش است
                            color = (0, 165, 255)
                            display_text = f"{track.name} - خارج از شیفت"
                        else:
                            # سبز: شناخته شد و در شیفت مجاز است؛ وضعیت ناحیه هم نمایش داده می‌شود
                            color = (0, 255, 0)
                            status_str = "داخل ناحیه" if track.inside_zone else "خارج از ناحیه"
                            display_text = f"{track.name} - {status_str}"

                        fx1, fy1, fx2, fy2 = map(int, face_bbox)
                        cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), color, 2)

                        font_size = 24
                        text_y = fy1 - 35 if fy1 - 35 > 10 else fy1 + 20

                        frame = put_persian_text(frame, display_text, (fx1, text_y), color=color, font_size=font_size)

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

                # 🔴 پنل وضعیت کنار هر دوربین؛ نیازی به آپدیت با فریم‌ریت ویدیو نیست
                now = time.time()
                for cam_id in active_cameras:
                    last = self.last_roster_emit_time.get(cam_id, 0)
                    if now - last >= 0.5:
                        self.last_roster_emit_time[cam_id] = now
                        roster = build_camera_roster(cam_id, recognizer, tracker)
                        self.roster_ready.emit(cam_id, roster)

                self.msleep(33) 

            except Exception as ex:
                print(f"\n❌ [CRITICAL ERROR in AI Thread]: {ex}")
                traceback.print_exc()

        stop_event.set()
        sender_thread.join()
        manager.stop_all()

        

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
        self.roster_labels = {}
        self.camera_containers = {}

        self.ai_engine = CentralAIEngineThread()
        self.ai_engine.frame_ready.connect(self.update_image, Qt.QueuedConnection)
        self.ai_engine.roster_ready.connect(self.update_roster, Qt.QueuedConnection)
        self.ai_engine.start()

        self.load_cameras()

    def request_reload_faces(self):
        """
        این متد رو از صفحات دیگه (لیست کارگران، افزودن کارگر) صدا بزن تا
        AI Thread چهره‌ها، شیفت‌ها و نواحی مجاز رو دوباره از دیتابیس بخونه،
        بدون نیاز به ری‌استارت کل برنامه.
        """
        self.ai_engine.cmd_queue.put({"action": "reload_faces"})

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

            roster_label = QLabel("در انتظار اطلاعات شیفت...")
            roster_label.setAlignment(Qt.AlignTop | Qt.AlignRight)
            roster_label.setWordWrap(True)
            roster_label.setTextFormat(Qt.RichText)
            roster_label.setStyleSheet(
                "background-color: #1e1e1e; color: white; border-radius: 5px; padding: 8px; font-size: 13px;"
            )
            roster_label.setFixedWidth(190)
            roster_label.setMinimumHeight(300)

            container = QFrame()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.addWidget(video_label, stretch=1)
            container_layout.addWidget(roster_label)

            self.active_labels[cam_id] = video_label
            self.roster_labels[cam_id] = roster_label
            self.camera_containers[cam_id] = container

            self.ai_engine.cmd_queue.put({"action": "add", "cam": cam_dict})
        else:
            self.ai_engine.cmd_queue.put({"action": "remove", "cam": cam_dict})
            if cam_id in self.camera_containers:
                widget_to_remove = self.camera_containers.pop(cam_id)
                self.video_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()
            self.active_labels.pop(cam_id, None)
            self.roster_labels.pop(cam_id, None)

        self.rearrange_video_grid()

    def update_image(self, cam_id, qt_img):
        if cam_id in self.active_labels:
            label = self.active_labels[cam_id]
            label.setPixmap(QPixmap.fromImage(qt_img))

    def update_roster(self, cam_id, roster):
        if cam_id not in self.roster_labels:
            return

        status_fa = {
            "inside": "داخل ناحیه",
            "outside": "خارج از ناحیه",
            "absent": "غایب",
            "off_shift": "خارج از شیفت",
        }

        if not roster:
            html = "کسی شیفتش الان جلوی این دوربین نیست."
        else:
            rows = []
            for item in roster:
                label_fa = status_fa.get(item["status"], item["status"])
                rows.append(
                    f'<div style="margin-bottom:6px;">'
                    f'<span style="color:{item["color"]};">●</span> {item["name"]}'
                    f'<br><span style="color:{item["color"]}; font-size:11px;">{label_fa}</span>'
                    f'</div>'
                )
            html = "".join(rows)

        self.roster_labels[cam_id].setText(html)

    def rearrange_video_grid(self):
        row, col = 0, 0
        for widget in self.camera_containers.values():
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