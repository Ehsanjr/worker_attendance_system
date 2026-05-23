from datetime import datetime, timedelta
import logging

class AttendanceLogic:
    def __init__(self, absent_timeout_seconds=10):
        # api_client حذف شد
        self.absent_timeout = timedelta(seconds=absent_timeout_seconds)

    def process_tracks(self, tracks):
        events = []
        now = datetime.now()
        for tr in tracks.values():
            event = self._check_track(tr, now)
            if event:
                events.append(event)
        return events

    def _check_track(self, track, now):
        # ENTER
        if track.inside_zone and not track.enter_sent:
            track.enter_sent = True
            track.exit_sent = False
            track.absent_sent = False
            logging.info(f"{track.name} entered zone (Cam {track.camera_id})")
            return {"event_type": "enter", "employee_id": track.employee_id, "camera_id": track.camera_id, "track_id": track.track_id, "timestamp": now.isoformat()}

        # EXIT
        if not track.inside_zone and track.enter_sent and not track.exit_sent:
            track.exit_sent = True
            track.enter_sent = False
            track.absent_sent = False
            track.last_outside_zone_time = now
            logging.info(f"{track.name} exited zone (Cam {track.camera_id})")
            return {"event_type": "exit", "employee_id": track.employee_id, "camera_id": track.camera_id, "track_id": track.track_id, "timestamp": now.isoformat()}

        # ABSENT
        if not track.inside_zone and track.last_outside_zone_time is not None and not track.absent_sent:
            if now - track.last_outside_zone_time > self.absent_timeout:
                track.absent_sent = True
                logging.info(f"{track.name} absent (Cam {track.camera_id})")
                return {"event_type": "absent", "employee_id": track.employee_id, "camera_id": track.camera_id, "track_id": track.track_id, "timestamp": now.isoformat()}

        return None
