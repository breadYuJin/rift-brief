"""대회가 끝난 뒤 따로 발표되는 상(파이널 MVP 등).

경기마다 주최 측이 뽑는 선수(LCK 의 POM, 국제 대회의 경기 MVP)와는 다른 상이다. 결승 경기의 기록에
적힌 선수와 같은 사람일 때가 많지만 같은 상은 아니므로, 경기 기록에서 미루어 붙이지 않는다.
보도로 확인한 것만 저장소 맨 위의 awards.json 에 손으로 적고, 여기서는 그 상을 해당 결승 경기에 잇는다.

결과는 data/awards.json 에 경기 ID 별로 저장한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import Match

SOURCE_PATH = Path(__file__).resolve().parents[1] / "awards.json"
REQUIRED = ("league", "final_date", "award", "player", "source")


def load(path: Path | None = None) -> list[dict[str, Any]]:
    try:
        raw = json.loads((path or SOURCE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    # 출처가 없는 항목은 쓰지 않는다.
    return [a for a in raw.get("awards") or [] if all(str(a.get(k) or "").strip() for k in REQUIRED)]


def resolve(awards: list[dict[str, Any]], matches: list[Match]) -> tuple[dict[str, dict[str, str]], list[str]]:
    """상을 결승 경기에 잇는다. (경기 ID → 상, 잇지 못한 항목 설명) 을 돌려준다.

    같은 대회·같은 날에 시작한 결승이 정확히 하나일 때만 잇는다.
    """
    out: dict[str, dict[str, str]] = {}
    missed: list[str] = []
    for a in awards:
        finals = [
            m
            for m in matches
            if m.league == a["league"] and m.round == "결승" and (m.begin_at or "")[:10] == a["final_date"]
        ]
        if len(finals) != 1:
            missed.append(f"{a['league']} {a['final_date']} {a['award']} (결승 {len(finals)}경기)")
            continue
        out[str(finals[0].id)] = {"award": a["award"], "player": a["player"], "source": a["source"]}
    return out, missed


def save(data_dir: Path, matches: list[Match], path: Path | None = None) -> bool:
    resolved, missed = resolve(load(path), matches)
    for line in missed:
        print(f"[상] 결승 경기를 찾지 못함: {line}")
    target = data_dir / "awards.json"
    text = json.dumps(resolved, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    if target.exists() and target.read_text(encoding="utf-8") == text:
        return False
    target.write_text(text, encoding="utf-8")
    return True
