import time
from dataclasses import dataclass, field


def _bbox_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    x1 = max(ax, bx)
    y1 = max(ay, by)
    x2 = min(ax + aw, bx + bw)
    y2 = min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter <= 0:
        return 0.0
    union = (aw * ah) + (bw * bh) - inter
    return inter / union if union > 0 else 0.0


def _centroid_dist(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    cx1, cy1 = ax + aw * 0.5, ay + ah * 0.5
    cx2, cy2 = bx + bw * 0.5, by + bh * 0.5
    return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5


@dataclass
class TrackedFace:
    track_id: int
    bbox: tuple[int, int, int, int]
    raw_face: object
    score: float
    first_seen_time: float = field(default_factory=time.monotonic)
    last_seen_time: float = field(default_factory=time.monotonic)
    last_embed_time: float = 0.0
    pending_uid: str | None = None
    confirm_count: int = 0
    matched_uid: str | None = None
    matched_person: dict | None = None
    confidence: float = 0.0
    event_sent: bool = False
    unknown_sent_time: float = 0.0
    notice_text: str = ""
    notice_level: str = "neutral"

    def needs_embedding(self, now: float, revalidate_interval: float = 2.0) -> bool:
        if self.matched_uid is None:
            return (now - self.last_embed_time) >= 0.25
        return (now - self.last_embed_time) >= revalidate_interval


class FaceTracker:
    """Rastreamento multi-rosto leve por IoU e proximidade para evitar reprocessamento SFace."""

    def __init__(self, max_lost_seconds: float = 0.9):
        self.max_lost_seconds = max_lost_seconds
        self._next_id = 1
        self.tracks: dict[int, TrackedFace] = {}

    def update(self, detections: list[tuple[tuple[int, int, int, int], object, float]], now: float | None = None) -> list[TrackedFace]:
        now = now or time.monotonic()

        for tid in list(self.tracks.keys()):
            if (now - self.tracks[tid].last_seen_time) > self.max_lost_seconds:
                del self.tracks[tid]

        unmatched_tracks = set(self.tracks.keys())
        matched_result: list[TrackedFace] = []

        for bbox, raw_face, score in detections:
            best_tid = None
            best_metric = 0.0
            diag = max(40.0, (bbox[2] ** 2 + bbox[3] ** 2) ** 0.5)

            for tid in unmatched_tracks:
                track = self.tracks[tid]
                iou = _bbox_iou(bbox, track.bbox)
                dist = _centroid_dist(bbox, track.bbox) / diag
                if iou >= 0.25 or dist <= 0.65:
                    metric = iou + max(0.0, 1.0 - dist) * 0.4
                    if metric > best_metric:
                        best_metric = metric
                        best_tid = tid

            if best_tid is not None:
                unmatched_tracks.remove(best_tid)
                tr = self.tracks[best_tid]
                tr.bbox = bbox
                tr.raw_face = raw_face
                tr.score = score
                tr.last_seen_time = now
                matched_result.append(tr)
            else:
                tid = self._next_id
                self._next_id += 1
                tr = TrackedFace(
                    track_id=tid,
                    bbox=bbox,
                    raw_face=raw_face,
                    score=score,
                    first_seen_time=now,
                    last_seen_time=now,
                )
                self.tracks[tid] = tr
                matched_result.append(tr)

        return matched_result
