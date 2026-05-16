from datetime import datetime, timedelta


class Track:

    def __init__(
        self,
        track_id,
        name,
        bbox,
        camera_id
    ):

        self.track_id = track_id
        self.name = name
        self.bbox = bbox
        self.camera_id = camera_id
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()

        self.inside_zone = False
        self.enter_sent = False
        self.exit_sent = False
        self.absent_sent = False
        self.last_outside_zone_time = None

    def __repr__(self):

        return (
            f"Track("
            f"id={self.track_id}, "
            f"name={self.name}, "
            f"camera={self.camera_id}, "
            f"inside_zone={self.inside_zone}"
            f")"
        )


class SimpleTracker:

    def __init__(self, iou_threshold=0.3):

        self.tracks = {}
        self.next_track_id = 1
        self.iou_threshold = iou_threshold

    def get_center(self, bbox):

        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        return (cx, cy)

    def is_inside_zone(self, bbox, zone):

        cx, cy = self.get_center(bbox)

        zx1, zy1, zx2, zy2 = zone

        return zx1 <= cx <= zx2 and zy1 <= cy <= zy2

    # -------------------------
    # IoU calculation
    # -------------------------

    def compute_iou(self, boxA, boxB):

        ax1, ay1, ax2, ay2 = boxA
        bx1, by1, bx2, by2 = boxB

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

        if union == 0:
            return 0

        return inter_area / union

    # -------------------------
    # find best track by IoU
    # -------------------------

    def find_best_track(self, bbox, camera_id):

        best_track = None
        best_iou = 0

        for track in self.tracks.values():

            if track.camera_id != camera_id:
                continue

            iou = self.compute_iou(bbox, track.bbox)

            if iou > best_iou:
                best_iou = iou
                best_track = track

        if best_iou >= self.iou_threshold:
            return best_track

        return None

    # -------------------------
    # update tracker
    # -------------------------

    def update(
        self,
        camera_id,
        name,
        bbox,
        zone
    ):

        track = self.find_best_track(bbox, camera_id)

        if track is None:

            track = Track(
                track_id=self.next_track_id,
                name=name,
                bbox=bbox,
                camera_id=camera_id
            )

            self.tracks[self.next_track_id] = track
            self.next_track_id += 1

        else:

            track.bbox = bbox
            track.last_seen = datetime.now()

            # اگر قبلاً unknown بود ولی الان شناخته شد
            if track.name == "unknown" and name != "unknown":
                track.name = name

        inside = self.is_inside_zone(bbox, zone)

        track.inside_zone = inside

        return track

    # -------------------------
    # cleanup old tracks
    # -------------------------

    def cleanup_tracks(self, max_missing_seconds=60):

        now = datetime.now()

        to_delete = []

        for track_id, track in self.tracks.items():

            missing_time = now - track.last_seen

            if missing_time > timedelta(seconds=max_missing_seconds):
                to_delete.append(track_id)

        for track_id in to_delete:
            del self.tracks[track_id]
