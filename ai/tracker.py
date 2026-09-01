from datetime import datetime, timedelta
from collections import deque
import numpy as np


class KalmanBoxTracker:
    """
    فیلترِ کالمنِ سبک برای مدل‌سازیِ حرکتِ یک باکس (بدونِ نیاز به کتابخانه‌ی
    خارجی مثل filterpy/scipy — فقط numpy).

    مدل: سرعتِ ثابت روی مرکز و مساحتِ باکس (همان رویکردِ استانداردِ SORT).
    بردارِ حالت: [cx, cy, s, r, vx, vy, vs]
        cx, cy = مرکزِ باکس | s = مساحت (w*h) | r = نسبتِ ابعاد (w/h, ثابت فرض می‌شود)
        vx, vy, vs = سرعتِ تغییرِ هرکدام

    چرا لازم است: اگر تراکر فقط با آخرین موقعیتِ *مشاهده‌شده* (خامِ فریمِ قبل)
    IoU بگیرد، وقتی بینِ دو چرخه‌ی تشخیص فرد جابه‌جا شود یا یک فریم را از دست
    بدهد، آن موقعیتِ خام دیگر دقیق نیست و تطبیق‌ها به‌راحتی اشتباه می‌شوند.
    اینجا هر ترک، حرکتش را جلو پیش‌بینی می‌کند (predict) و مقایسه‌ی IoU با
    موقعیتِ *پیش‌بینی‌شده* انجام می‌شود، نه موقعیتِ کهنه.
    """

    def __init__(self, bbox):
        self.ndim = 7
        self.x = np.zeros((self.ndim, 1))

        z = self._bbox_to_z(bbox)
        self.x[:4] = z
        self.x[4:] = 0.0

        # ماتریسِ انتقالِ حالت: cx+=vx ، cy+=vy ، s+=vs ، r ثابت
        self.F = np.eye(self.ndim)
        self.F[0, 4] = 1.0
        self.F[1, 5] = 1.0
        self.F[2, 6] = 1.0

        # ماتریسِ اندازه‌گیری: فقط cx,cy,s,r مستقیم قابلِ مشاهده‌اند
        self.H = np.zeros((4, self.ndim))
        self.H[0, 0] = self.H[1, 1] = self.H[2, 2] = self.H[3, 3] = 1.0

        # نویزِ اندازه‌گیری (به مساحت/نسبتِ ابعاد کمی بی‌اعتمادتریم)
        self.R = np.eye(4)
        self.R[2:, 2:] *= 10.0

        # عدمِ قطعیتِ اولیه؛ برای سرعت‌ها خیلی بالاست چون هنوز چیزی از حرکتِ
        # واقعی نمی‌دانیم
        self.P = np.eye(self.ndim) * 10.0
        self.P[4:, 4:] *= 1000.0

        # نویزِ فرآیند (فرضِ حرکتِ نسبتاً یکنواخت بینِ دو فریمِ پردازش‌شده)
        self.Q = np.eye(self.ndim)
        self.Q[4:, 4:] *= 0.05
        self.Q[-1, -1] *= 0.2

        self.time_since_update = 0
        self.hit_streak = 0
        self.age = 0

    @staticmethod
    def _bbox_to_z(bbox):
        x1, y1, x2, y2 = bbox
        w, h = max(x2 - x1, 1e-3), max(y2 - y1, 1e-3)
        cx, cy = x1 + w / 2.0, y1 + h / 2.0
        s = w * h
        r = w / h
        return np.array([[cx], [cy], [s], [r]], dtype=np.float64)

    def get_state_bbox(self):
        cx, cy, s, r = self.x[0, 0], self.x[1, 0], self.x[2, 0], self.x[3, 0]
        s = max(s, 1.0)
        r = max(r, 1e-3)
        w = np.sqrt(s * r)
        h = s / w
        return [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0]

    def predict(self):
        """یک گامِ زمانی جلو می‌رود (بدونِ مشاهده‌ی جدید) و باکسِ پیش‌بینی‌شده را برمی‌گرداند."""
        if (self.x[2, 0] + self.x[6, 0]) <= 0:
            self.x[6, 0] = 0.0

        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

        self.age += 1
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1

        return self.get_state_bbox()

    def update(self, bbox):
        """با یک مشاهده‌ی واقعیِ جدید، تخمین را تصحیح می‌کند (گامِ correction کالمن)."""
        z = self._bbox_to_z(bbox)
        y = z - (self.H @ self.x)
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.P = (np.eye(self.ndim) - K @ self.H) @ self.P

        self.time_since_update = 0
        self.hit_streak += 1

        return self.get_state_bbox()


class Track:
    def __init__(self, track_id, name, bbox, camera_id, employee_id=None, confidence=0.0):
        self.track_id = track_id
        self.name = name
        self.employee_id = employee_id
        self.camera_id = camera_id
        self.confidence = confidence

        # حرکتِ باکس از فیلترِ کالمن (پیش‌بینی + تصحیح) می‌آید که در برابرِ
        # نویز و جاافتادنِ فریم مقاوم‌تر است
        self.kf = KalmanBoxTracker(bbox)
        self.bbox = self.kf.get_state_bbox()

        self.first_seen = datetime.now()
        self.last_seen = datetime.now()

        # هویت با اولین تشخیص برای همیشه "قفل" نمی‌شود؛ آخرین چند مشاهده‌ی
        # واقعیِ چهره اینجا نگه داشته می‌شود تا هویتِ نهایی بر اساسِ رأی‌گیریِ
        # وزن‌دار با اطمینان تعیین/تصحیح شود.
        self.identity_history = deque(maxlen=7)
        if employee_id:
            self.identity_history.append((employee_id, name, confidence))

        self.inside_zone = False
        self.enter_sent = False
        self.exit_sent = False
        self.absent_sent = False

        self.last_outside_zone_time = None

    def predict(self):
        """پیش‌بینیِ موقعیتِ این ترک برای فریمِ فعلی، قبل از تطبیق با تشخیص‌های تازه."""
        self.bbox = self.kf.predict()
        return self.bbox

    def apply_detection(self, bbox):
        """تصحیحِ فیلترِ کالمن با یک تشخیصِ واقعیِ این فریم."""
        self.bbox = self.kf.update(bbox)
        self.last_seen = datetime.now()

    def observe_identity(self, employee_id, name, confidence):
        """
        هر بار که این فریم واقعاً یک چهره‌ی شناخته‌شده برای این ترک دیده شده،
        این مشاهده وارد تاریخچه می‌شود و هویتِ نهاییِ ترک از نو محاسبه می‌شود.
        این‌طوری اگر ترک از ابتدا اشتباه شناسایی شده باشد (مثلاً یک فریمِ نویزی)،
        با چند مشاهده‌ی پیاپیِ درست، خودش را تصحیح می‌کند؛ ولی یک تشخیصِ تک‌فریمیِ
        اشتباه نمی‌تواند هویتِ درستِ از قبل تثبیت‌شده را فوراً خراب کند.

        🔴 این تابع تنها راهِ عوض‌شدنِ نام/employee_id یک ترک است. مسیرِ دیگری
        برای «مستقیم overwrite کردنِ» هویت وجود ندارد (برخلافِ نسخه‌ی قبلی که
        در update() ساده یک تشخیصِ تک‌فریمی می‌توانست بی‌هیچ رأی‌گیری‌ای هویت را
        عوض کند).
        """
        if not employee_id:
            return

        self.identity_history.append((employee_id, name, confidence))

        scores, counts, names = {}, {}, {}
        for emp_id, nm, conf in self.identity_history:
            scores[emp_id] = scores.get(emp_id, 0.0) + conf
            counts[emp_id] = counts.get(emp_id, 0) + 1
            names[emp_id] = nm

        best_emp_id = max(scores, key=scores.get)
        best_count = counts[best_emp_id]
        best_avg_conf = scores[best_emp_id] / best_count

        if self.employee_id is None:
            # ترکِ تازه (هنوز هیچ هویتی ندارد). فقط وقتی هویت را قطعی می‌کنیم
            # که یا اطمینانِ خیلی بالایی داشته باشیم (تشخیصِ تمیز)، یا حداقل
            # دوبار پشتِ‌هم همین هویت دیده شده باشد؛ در غیرِ این صورت ترک
            # همچنان "ناشناس" می‌ماند تا مشاهده‌ی بعدی.
            STRONG_CONFIDENCE = 0.6  # با لاگ‌های [DEBUG] در face_recognition.py روی داده‌ی واقعی کالیبره کنید
            if best_avg_conf >= STRONG_CONFIDENCE or best_count >= 2:
                self.employee_id = best_emp_id
                self.name = names[best_emp_id]
                self.confidence = best_avg_conf
            return

        if best_emp_id != self.employee_id:
            min_needed = max(2, (len(self.identity_history) // 2) + 1)
            if counts[best_emp_id] >= min_needed:
                self.employee_id = best_emp_id
                self.name = names[best_emp_id]
                self.confidence = scores[best_emp_id] / counts[best_emp_id]

    def __repr__(self):
        return (
            f"Track(id={self.track_id}, name={self.name}, employee_id={self.employee_id}, "
            f"camera={self.camera_id}, inside_zone={self.inside_zone})"
        )


class SimpleTracker:
    """
    🔴 نکته‌ی مهمِ استفاده: این تراکر فقط با جریانِ زیر درست کار می‌کند —
    برای هر دوربین، در هر چرخه‌ی تشخیص، دقیقاً به همین ترتیب صدا بزنید:

        tracker.predict_camera_tracks(camera_id)
        matches = tracker.match_bodies_to_tracks(camera_id, list_of_bboxes)
        for i, bbox in enumerate(list_of_bboxes):
            track = tracker.update_matched(
                matches.get(i), camera_id=camera_id, name=..., employee_id=...,
                confidence=..., bbox=bbox, inside_zone=...
            )

    هرگز به ازای هر باکس/تشخیص جداگانه و مستقل صدا نزنید (مثلاً در یک حلقه‌ی
    ساده‌ی for بدون predict/match قبلی) — این دقیقاً همان الگویی بود که در
    نسخه‌ی قبلی باعث می‌شد وقتی دو نفر نزدیک هم‌اند، هر دو باکسِ بدنشان به یک
    ترکِ نزدیک‌تر بچسبند و هویتشان بینشان جابه‌جا شود (چون هر باکس مستقل و
    بدونِ اطلاع از باکس‌های دیگرِ همان فریم، نزدیک‌ترین ترک را برمی‌داشت).
    match_bodies_to_tracks هر ترک و هر باکس را حداکثر یک‌بار در هر فریم مصرف
    می‌کند، پس این تداخل دیگر رخ نمی‌دهد.
    """

    def __init__(self, iou_threshold=0.3):
        self.tracks = {}
        self.next_track_id = 1
        self.iou_threshold = iou_threshold

    @staticmethod
    def compute_iou(A, B):
        ax1, ay1, ax2, ay2 = A
        bx1, by1, bx2, by2 = B

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        areaA = (ax2 - ax1) * (ay2 - ay1)
        areaB = (bx2 - bx1) * (by2 - by1)
        union = areaA + areaB - inter_area

        return inter_area / union if union else 0

    def predict_camera_tracks(self, camera_id):
        """
        قدمِ «پیش‌بینی» کالمن: قبل از تطبیقِ تشخیص‌های این فریم، همه‌ی
        ترک‌های این دوربین یک گام جلو برده می‌شوند (بر اساسِ سرعتِ تخمینی‌شان)
        تا مقایسه‌ی IoU با موقعیتِ *به‌روزشده*، نه موقعیتِ کهنه‌ی فریمِ قبل، انجام شود.
        باید همیشه دقیقاً یک‌بار در ابتدایِ هر چرخه‌ی تشخیص برای هر دوربین صدا زده شود.
        """
        for tr in self.tracks.values():
            if tr.camera_id == camera_id:
                tr.predict()

    def match_bodies_to_tracks(self, camera_id, bboxes):
        """
        تطبیقِ سراسری بین باکس‌های بدنِ این فریم با موقعیتِ *پیش‌بینی‌شده*ی
        ترک‌های موجودِ همین دوربین (predict_camera_tracks باید قبلش صدا زده
        شده باشد). به‌جای تطبیقِ یکی‌یکی به هر ترتیبی که YOLO باکس‌ها را می‌دهد،
        همه‌ی جفت‌های ممکنِ (باکس، ترک) را بر اساس IoU مرتب می‌کنیم و از
        بیشترین IoU شروع به تخصیص می‌کنیم؛ هر باکس و هر ترک فقط یک‌بار مصرف می‌شود
        (یعنی وقتی دو نفر نزدیک هم‌اند، دو باکسشان نمی‌توانند هر دو به یک ترک بچسبند).

        خروجی: دیکشنری bbox_index -> Track (باکس‌هایی که تطبیق پیدا نکردند در آن نیستند)
        """
        candidate_tracks = [tr for tr in self.tracks.values() if tr.camera_id == camera_id]
        pairs = []
        for i, bbox in enumerate(bboxes):
            for tr in candidate_tracks:
                iou = self.compute_iou(bbox, tr.bbox)
                if iou >= self.iou_threshold:
                    pairs.append((iou, i, tr))

        pairs.sort(key=lambda p: p[0], reverse=True)

        assigned_idx = set()
        assigned_track_ids = set()
        result = {}

        for iou, i, tr in pairs:
            if i in assigned_idx or tr.track_id in assigned_track_ids:
                continue
            result[i] = tr
            assigned_idx.add(i)
            assigned_track_ids.add(tr.track_id)

        return result

    def update_matched(self, matched_track, camera_id, name, bbox, employee_id, confidence=0.0, inside_zone=False):
        """
        تطبیق از قبل (توسط match_bodies_to_tracks) مشخص شده: matched_track یا
        ترکِ همین شخص است یا None (یعنی ترکِ جدید بساز).
        """
        if matched_track is None:
            track = Track(
                track_id=self.next_track_id,
                name=name,
                bbox=bbox,
                camera_id=camera_id,
                employee_id=employee_id,
                confidence=confidence
            )
            self.tracks[self.next_track_id] = track
            self.next_track_id += 1
        else:
            track = matched_track
            # تصحیحِ کالمن با مشاهده‌ی واقعیِ این فریم (نه جایگزینیِ خام)
            track.apply_detection(bbox)
            # هویت فقط از طریقِ رأی‌گیریِ observe_identity عوض می‌شود، نه overwrite مستقیم
            track.observe_identity(employee_id, name, confidence)

        track.inside_zone = inside_zone
        return track

    def cleanup_tracks(self, max_missing_seconds=15):
        # این عدد باید همیشه از absent_timeout_seconds در AttendanceLogic
        # (پیش‌فرض ۱۰ ثانیه) بزرگ‌تر بماند؛ وگرنه ممکن است ترکی که هنوز فرصتِ
        # ثبتِ رویدادِ «غایب» را نداشته، قبل از آن رویداد پاک شود.
        now = datetime.now()
        to_delete = [
            tid for tid, tr in self.tracks.items()
            if now - tr.last_seen > timedelta(seconds=max_missing_seconds)
        ]
        for tid in to_delete:
            del self.tracks[tid]