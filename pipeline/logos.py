"""팀 로고 주소 수집.

1순위는 LoL e스포츠 공식 사이트(lolesports.com)가 쓰는 팀 목록이다. 로고 파일은 공식 이미지 서버
(static.lolesports.com)에 있고, 사이트는 그 주소를 그대로 불러 쓴다(파일을 복사해 두지 않는다).
이 팀 목록 API 는 공개 문서가 없는 것이라 형식이 바뀌거나 막힐 수 있다. 그때는 2순위로
Leaguepedia 에 올라와 있는 팀 로고 파일 주소를 쓴다. 둘 다 못 찾은 팀은 지금처럼 약칭만 보인다.

결과는 data/teams.json 에 팀 ID 별로 저장한다. 한 번 찾은 로고는 다음에 못 찾아도 지우지 않는다.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests

from .leaguepedia import Cargo, resolve_team

LOLESPORTS_URL = "https://esports-api.lolesports.com/persisted/gw/getTeams"
# lolesports.com 웹 화면이 공개적으로 쓰는 키. 바뀌면 LOLESPORTS_API_KEY 로 덮어쓴다.
LOLESPORTS_KEY = os.getenv("LOLESPORTS_API_KEY") or "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
_DROP_WORDS = ("esports", "esport", "gaming", "team")


def norm(name: str) -> str:
    """이름 비교용 키: 소문자 영문·숫자만, 흔한 꼬리말(Esports 등)은 뗀다."""
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    for word in _DROP_WORDS:
        if key.endswith(word) and len(key) > len(word) + 1:
            key = key[: -len(word)]
    return key


def our_teams(raw: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """수집한 시즌 기록에 나오는 팀: ID → 약칭과 영어 이름들."""
    teams: dict[int, dict[str, Any]] = {}
    for league in raw["leagues"].values():
        shorts = {t["Name"]: t["Short"] for t in league.get("teams") or [] if t.get("Short")}
        for row in league.get("matches") or []:
            for name in ((row.get("Team1") or "").strip(), (row.get("Team2") or "").strip()):
                if not name or name.upper() == "TBD":
                    continue
                team = resolve_team(name, shorts)
                entry = teams.setdefault(team.id, {"acronym": team.acronym, "names": set()})
                entry["names"].add(name)
    return teams


def https(url: str) -> str:
    """https 로 바꾸고, 주소에 섞인 공백 같은 글자를 안전하게 바꾼다."""
    return quote(re.sub(r"^http://", "https://", url.strip()), safe=":/?&=%+,;@()!*'~-._")


def _lolesports_get() -> list[dict[str, Any]]:
    r = requests.get(LOLESPORTS_URL, params={"hl": "en-US"}, headers={"x-api-key": LOLESPORTS_KEY}, timeout=60)
    r.raise_for_status()
    return r.json()["data"]["teams"]


def match_lolesports(teams: dict[int, dict[str, Any]], official: list[dict[str, Any]]) -> dict[int, str]:
    """공식 팀 목록에서 우리 팀을 찾는다. 이름이 같으면 가장 확실하고, 아니면 약칭이 같은 현역 팀을 쓴다."""
    usable = [t for t in official if t.get("image") and t.get("name")]
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in usable:
        by_name[norm(t["name"])].append(t)
        by_code[(t.get("code") or "").upper()].append(t)

    def active_first(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(items, key=lambda t: t.get("status") != "active")

    out: dict[int, str] = {}
    for team_id, team in teams.items():
        keys = {norm(n) for n in team["names"]}
        named = [t for k in keys for t in by_name.get(k, [])]
        coded = by_code.get(team["acronym"].upper(), [])
        both = [t for t in named if t in coded]
        # 후원사 이름이 붙어 표기가 다른 경우(Cloud9 ↔ Cloud9 Kia): 약칭이 같고 이름이 서로의 앞부분이면 같은 팀으로 본다.
        close = [
            t for t in coded
            if any(len(k) >= 2 and (norm(t["name"]).startswith(k) or k.startswith(norm(t["name"]))) for k in keys)
        ]
        active_coded = [t for t in coded if t.get("status") == "active"]
        # 약칭만 같은 경우는 현역 팀이 하나뿐일 때만 믿는다(2군·해체 팀과 약칭이 겹칠 수 있다).
        pick = (
            active_first(both) or active_first(named) or active_first(close)
            or (active_coded if len(active_coded) == 1 else [])
        )
        if pick:
            out[team_id] = https(pick[0]["image"])
        if os.getenv("LOGO_DEBUG"):
            print(f"[로고] {team['acronym']} {sorted(team['names'])} → {pick[0]['name'] if pick else '못 찾음'}")
            for t in coded[:8]:
                print(f"         약칭 후보: {t['name']} / {t.get('status')} / {(t.get('homeLeague') or {}).get('name')} / {t['image']}")
    return out


def from_leaguepedia(teams: dict[int, dict[str, Any]], cargo: Any) -> dict[int, str]:
    """Leaguepedia 팀 문서에 걸린 로고 파일의 주소."""
    names = sorted({n for t in teams.values() for n in t["names"]})
    if not names:
        return {}
    quoted = ",".join('"' + n.replace('"', '\\"') + '"' for n in names)
    rows = cargo.query(tables="Teams", fields="Name,Image", where=f"Name IN ({quoted})", order_by="Name")
    file_of = {r["Name"]: r["Image"] for r in rows if r.get("Image")}
    urls = cargo.image_urls(sorted(set(file_of.values())))
    out: dict[int, str] = {}
    for team_id, team in teams.items():
        for name in sorted(team["names"]):
            url = urls.get(file_of.get(name, ""))
            if url:
                out[team_id] = https(url)
                break
    return out


def is_image(url: str) -> bool:
    """그 주소가 실제로 그림을 돌려주는지. 그림 서버가 종류를 안 알려 주는 경우가 있어 파일 앞머리도 본다."""
    try:
        r = requests.get(url, stream=True, timeout=30, headers={"User-Agent": "Mozilla/5.0 (rift-brief logo check)"})
        head = next(r.iter_content(16), b"") if r.status_code == 200 else b""
        kind = r.headers.get("content-type", "")
        r.close()
    except requests.RequestException as exc:
        if os.getenv("LOGO_DEBUG"):
            print(f"[로고] 열기 실패 {url}: {exc}")
        return False
    magic = head.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8", b"RIFF")) or b"<svg" in head or head.startswith(b"<?xml")
    ok = r.status_code == 200 and (kind.startswith("image/") or magic)
    if not ok and os.getenv("LOGO_DEBUG"):
        print(f"[로고] 그림 아님 {url}: HTTP {r.status_code}, {kind!r}, {head[:8]!r}")
    return ok


def collect(
    data_dir: Path,
    year: int,
    *,
    official: Callable[[], list[dict[str, Any]]] = _lolesports_get,
    cargo: Any = None,
    check: Callable[[str], bool] = is_image,
) -> str:
    raw = json.loads((data_dir / "raw" / f"leaguepedia-{year}.json").read_text(encoding="utf-8"))
    teams = our_teams(raw)
    path = data_dir / "teams.json"
    saved: dict[str, Any] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    found: dict[int, tuple[str, str]] = {}
    notes: list[str] = []
    try:
        for team_id, url in match_lolesports(teams, official()).items():
            found[team_id] = (url, "lolesports")
    except Exception as exc:
        notes.append(f"공식 목록 실패({str(exc)[:80]})")
    missing = {i: t for i, t in teams.items() if i not in found}
    if missing:
        try:
            for team_id, url in from_leaguepedia(missing, cargo or Cargo()).items():
                found[team_id] = (url, "leaguepedia")
        except Exception as exc:
            notes.append(f"Leaguepedia 실패({str(exc)[:80]})")

    broken = 0
    for team_id, (url, source) in found.items():
        old = saved.get(str(team_id), {})
        if old.get("logo") == url or check(url):  # 이미 확인한 주소는 다시 받아 보지 않는다.
            saved[str(team_id)] = {"acronym": teams[team_id]["acronym"], "logo": url, "source": source}
        else:
            broken += 1
    path.write_text(json.dumps(dict(sorted(saved.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    have = [i for i in teams if str(i) in saved]
    by_source = defaultdict(int)
    for i in have:
        by_source[saved[str(i)]["source"]] += 1
    without = sorted(teams[i]["acronym"] for i in teams if str(i) not in saved)
    summary = f"{len(teams)}팀 중 {len(have)}팀 (공식 {by_source['lolesports']}, Leaguepedia {by_source['leaguepedia']})"
    if without:
        summary += f", 없음: {', '.join(without)}"
    if broken:
        summary += f", 열리지 않는 주소 {broken}개"
    return summary + ("".join(f", {n}" for n in notes))
