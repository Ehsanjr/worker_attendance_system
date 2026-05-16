from datetime import datetime, timedelta
import logging


class AttendanceLogic:
    def __init__(self, absent_timeout_seconds=10):
        self.absent_timeout = timedelta(seconds=absent_timeout_seconds)

    def process_tracks(self, tracks):
        events = []
        now = datetime.now()

        for track in tracks.values():
            event = self._check_track(track, now)
            if event:
                events.append(event)

        return events

    def _check_track(self, track, now):
        # ورود
        if track.inside_zone and not track.enter_sent:
            track.enter_sent = True
            track.exit_sent = False
            track.absent_sent = False

            logging.info(f"{track.name} entered zone (Camera {track.camera_id})")

            return {
                "event": "enter",
                "name": track.name,
                "track_id": track.track_id,
                "time": now.isoformat(),
            }

        # خروج
        if not track.inside_zone and not track.exit_sent and track.enter_sent:
            track.exit_sent = True
            track.enter_sent = False
            track.absent_sent = False
            track.last_outside_zone_time = now

            logging.info(f"{track.name} exited zone (Camera {track.camera_id})")

            return {
                "event": "exit",
                "name": track.name,
                "track_id": track.track_id,
                "time": now.isoformat(),
            }

        # غیبت
        if not track.inside_zone and track.last_outside_zone_time is not None:
    
            not_seen_duration = now - track.last_outside_zone_time

            if not_seen_duration > self.absent_timeout and not track.absent_sent:
                track.absent_sent = True
                return{
                    "event": "absent",
                    "name": track.name,
                    "track_id": track.track_id,
                    "time": now.isoformat(),
                }


        return None
