"""공식 채널(@LCK)의 영상 목록 수집.

YouTube Data API 로 채널에 올라온 영상의 제목·설명·길이와, 생중계였다면 실제 방송 시작·종료 시각을 받는다.
방송 시작 시각과 경기의 실제 시작 시각을 맞추면 "풀 다시보기에서 이 킬이 나오는 위치"를 계산할 수 있다.

YOUTUBE_API_KEY 가 없으면 아무것도 하지 않는다. 받은 목록은 data/raw/videos-<연도>.json 에 쌓인다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import requests

API = "https://www.googleapis.com/youtube/v3"
CHANNEL_HANDLE = os.getenv("YOUTUBE_CHANNEL", "@LCK")
MAX_PAGES = int(os.getenv("YOUTUBE_MAX_PAGES", "6"))  # 한 번에 최근 50×N 개까지 본다

Get = Callable[[str, dict[str, Any]], dict[str, Any]]


def _http_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    r = requests.get(f"{API}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def uploads_playlist(key: str, get: Get = _http_get, handle: str = CHANNEL_HANDLE) -> str:
    data = get("channels", {"part": "contentDetails", "forHandle": handle, "key": key})
    items = data.get("items") or []
    if not items:
        raise RuntimeError(f"채널 {handle} 을 찾지 못했습니다.")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_videos(key: str, known: dict[str, Any], get: Get = _http_get, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """최근 영상부터 훑어 아직 없는 영상의 정보를 known 에 더해 돌려준다."""
    playlist = uploads_playlist(key, get)
    new_ids: list[str] = []
    token = None
    for _ in range(max_pages):
        params = {"part": "contentDetails", "playlistId": playlist, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        page = get("playlistItems", params)
        ids = [i["contentDetails"]["videoId"] for i in page.get("items") or []]
        fresh = [i for i in ids if i not in known]
        new_ids += fresh
        token = page.get("nextPageToken")
        if not token or len(fresh) < len(ids):  # 이미 아는 영상이 나오면 그 뒤는 전에 받은 것이다.
            break
    for start in range(0, len(new_ids), 50):
        batch = new_ids[start : start + 50]
        data = get("videos", {"part": "snippet,contentDetails,liveStreamingDetails", "id": ",".join(batch), "key": key})
        for v in data.get("items") or []:
            live = v.get("liveStreamingDetails") or {}
            known[v["id"]] = {
                "title": v["snippet"].get("title", ""),
                "published": v["snippet"].get("publishedAt", ""),
                "description": v["snippet"].get("description", ""),
                "duration": v["contentDetails"].get("duration", ""),
                "live_start": live.get("actualStartTime"),
                "live_end": live.get("actualEndTime"),
            }
    return known


def collect(data_dir: Path, year: int, get: Get = _http_get) -> str:
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key:
        return "건너뜀: YOUTUBE_API_KEY 없음"
    path = data_dir / "raw" / f"videos-{year}.json"
    known = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    before = len(known)
    known = fetch_videos(key, known, get)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(known, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    streams = sum(1 for v in known.values() if v.get("live_start"))
    return f"영상 {len(known)}개 (새로 {len(known) - before}개, 생중계 다시보기 {streams}개)"


def load_videos(data_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path in sorted((data_dir / "raw").glob("videos-*.json")):
        out.update(json.loads(path.read_text(encoding="utf-8")))
    return out
