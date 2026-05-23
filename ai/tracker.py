from datetime import datetime, timedelta


class Track:

    def __init__(self, track_id, name, bbox, camera_id, employee_id=None):
        self.track_id = track_id
        self.name = name
        self.employee_id = employee_id
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
            f"Track(id={self.track_id}, name={self.name}, id={self.employee_id}, "
            f"camera={self.camera_id}, inside_zone={self.inside_zone})"
        )


class SimpleTracker:

    def __init__(self, iou_threshold=0.3):
        self.tracks = {}
        self.next_track_id = 1
        self.iou_threshold = iou_threshold

    def compute_iou(self, A, B):
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

    def find_best_track(self, bbox, camera_id):
        best, best_iou = None, 0

        for tr in self.tracks.values():
            if tr.camera_id != camera_id:
                continue
            iou = self.compute_iou(bbox, tr.bbox)
            if iou > best_iou:
                best_iou, best = iou, tr

        return best if best_iou >= self.iou_threshold else None

    def update(self, camera_id, name, bbox, zone, employee_id):
        track = self.find_best_track(bbox, camera_id)

        if track is None:
            track = Track(
                track_id=self.next_track_id,
                name=name,
                bbox=bbox,
                camera_id=camera_id,
                employee_id=employee_id
            )
            self.tracks[self.next_track_id] = track
            self.next_track_id += 1
        else:
            track.bbox = bbox
            track.last_seen = datetime.now()

            if track.name == "unknown" and name != "unknown":
                track.name = name
                track.employee_id = employee_id

        # Check inside zone
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        zx1, zy1, zx2, zy2 = zone
        track.inside_zone = zx1 <= cx <= zx2 and zy1 <= cy <= zy2

        return track

    def cleanup_tracks(self, max_missing_seconds=60):
        now = datetime.now()
        to_delete = [
            tid for tid, tr in self.tracks.items()
            if now - tr.last_seen > timedelta(seconds=max_missing_seconds)
        ]
        for tid in to_delete:
            del self.tracks[tid]
