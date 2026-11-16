"""킬 장면의 영상 위치 계산.

  영상 위치(초) = 경기의 실제 시작 시각 + 킬이 난 경기 내 시각 − 방송의 실제 시작 시각 + 보정값

- 경기의 실제 시작 시각: 타임라인에 찍힌 실제 시각 기준점(anchors)
- 방송의 실제 시작 시각: YouTube 가 알려 주는 생중계 시작 시각(풀 다시보기 영상)
- 보정값: 중계 지연만큼의 초. HIGHLIGHT_OFFSET_SEC 로 준다.

경기 도중 일시정지가 길면 경기 내 시각과 실제 시각이 어긋나므로, 그런 세트는 링크를 만들지 않는다.
검증 전에는 사이트에 내보내지 않는다(HIGHLIGHT_LINKS=1 일 때만 내보낸다).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

MAX_DRIFT_SEC = 20  # 시작·종료 기준점으로 본 일시정지 합계가 이보다 크면 믿지 않는다
LEAD_SEC = 8  # 킬 직전부터 보이도록 앞당기는 시간


def enabled() -> bool:
    return os.getenv("HIGHLIGHT_LINKS", "") == "1"


def offset_sec() -> int:
    return int(os.getenv("HIGHLIGHT_OFFSET_SEC", "0") or 0)


def _epoch(iso: str | None) -> int | None:
    if not iso:
        return None
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def game_start(timeline: dict[str, Any]) -> int | None:
    """경기 0:00 의 실제 시각(epoch 초). 기준점이 없거나 일시정지로 어긋났으면 None."""
    anchors = timeline.get("anchors") or []
    if not anchors:
        return None
    starts = [real - t for t, real in anchors]
    if max(starts) - min(starts) > MAX_DRIFT_SEC:
        return None
    return min(starts)


def find_video(start: int, videos: dict[str, Any]) -> tuple[str, int] | None:
    """그 시각을 담고 있는 생중계 다시보기와 방송 시작 시각. 여러 개면 가장 늦게 시작한 방송을 고른다."""
    best: tuple[str, int] | None = None
    for video_id, v in videos.items():
        begin, end = _epoch(v.get("live_start")), _epoch(v.get("live_end"))
        if begin is None or end is None or not (begin <= start <= end):
            continue
        if best is None or begin > best[1]:
            best = (video_id, begin)
    return best


def clip_links(timeline: dict[str, Any], fights: list[dict[str, Any]], videos: dict[str, Any], shift: int | None = None) -> list[str | None]:
    """교전마다 영상 바로가기 주소. 만들 수 없으면 None."""
    start = game_start(timeline)
    found = find_video(start, videos) if start is not None else None
    if not found:
        return [None] * len(fights)
    video_id, stream_start = found
    shift = offset_sec() if shift is None else shift
    out: list[str | None] = []
    for f in fights:
        at = start + f["t"] - stream_start + shift - LEAD_SEC
        out.append(f"https://www.youtube.com/watch?v={video_id}&t={max(0, at)}s")
    return out
