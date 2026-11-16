"""자동 수집 진입점: `python -m pipeline.collect`

사이트를 갱신하는 데 필요한 자료를 수집원별로 받아 온다. 수집원 하나가 실패하거나 키가 없어도
나머지는 계속 돈다. 무엇을 받았고 무엇을 건너뛰었는지는 data/collect.json 에 남는다.

  수집원            받는 것                                      필요한 것
  leaguepedia       경기 결과·밴픽·세트/선수 기록·타임라인       (없음)
  champions         챔피언 한국어 이름표와 아이콘 주소           (없음)
  logos             팀 로고 주소                                 (없음)
  youtube           공식 채널(@LCK) 영상 목록과 방송 시각        YOUTUBE_API_KEY
  grid              실시간 밴픽·경기 진행                        GRID_API_KEY (아직 구현 전)

새 수집원은 SOURCES 에 한 줄을 더하면 된다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import champions, leaguepedia, logos, youtube
from .config import Settings


@dataclass(frozen=True)
class Source:
    name: str
    what: str
    needs: tuple[str, ...]  # 필요한 환경변수. 하나라도 없으면 건너뛴다.
    run: Callable[[Path, int], str]  # 요약 문장을 돌려준다. 실패하면 예외.


def _leaguepedia(data_dir: Path, year: int) -> str:
    code = leaguepedia.main(["--year", str(year)])
    if code != 0:
        raise RuntimeError("받은 경기가 없음")
    raw = json.loads((data_dir / "raw" / f"leaguepedia-{year}.json").read_text(encoding="utf-8"))
    games = sum(len(l.get("games") or []) for l in raw["leagues"].values())
    tl_path = data_dir / "raw" / f"timelines-{year}.json"
    timelines = sum(1 for v in json.loads(tl_path.read_text(encoding="utf-8")).values() if v) if tl_path.exists() else 0
    return f"세트 {games}개, 타임라인 {timelines}개"


def _champions(data_dir: Path, year: int) -> str:
    table = champions.fetch()
    champions.save(data_dir, table)
    sample = next(iter(table["champions"].values()))["id"]
    icons = "열림" if logos.is_image(f"{table['icon_base']}{sample}.png") else "열리지 않음"
    return f"패치 {table['version']}, 아이콘 {icons}"


def _grid(data_dir: Path, year: int) -> str:
    raise NotImplementedError("GRID 접근 권한을 받은 뒤 구현 (pipeline/live.py 의 GridFeed)")


SOURCES = [
    Source("leaguepedia", "경기 결과·밴픽·세트/선수 기록·타임라인", (), _leaguepedia),
    Source("champions", "챔피언 한국어 이름표와 아이콘", (), _champions),
    Source("logos", "팀 로고", (), logos.collect),
    Source("youtube", "공식 채널 영상 목록과 방송 시각", ("YOUTUBE_API_KEY",), youtube.collect),
    Source("grid", "실시간 밴픽·경기 진행", ("GRID_API_KEY",), _grid),
]


def run(data_dir: Path, year: int, only: list[str] | None = None, sources: list[Source] = SOURCES) -> dict[str, dict[str, str]]:
    status_path = data_dir / "collect.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status = {}
    for src in sources:
        if only and src.name not in only:
            continue
        missing = [k for k in src.needs if not os.getenv(k)]
        entry = {"what": src.what, "needs": ", ".join(src.needs)}
        if missing:
            entry |= {"state": "키 없음", "note": f"{', '.join(missing)} 를 넣으면 켜집니다."}
        else:
            try:
                entry |= {"state": "수집됨", "note": src.run(data_dir, year), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            except NotImplementedError as exc:
                entry |= {"state": "준비 중", "note": str(exc)}
            except Exception as exc:
                # 실패해도 지난번에 받은 자료는 그대로 남아 있다.
                entry |= {"state": "실패", "note": str(exc)[:200], "at": status.get(src.name, {}).get("at", "")}
        status[src.name] = entry
        print(f"[수집] {src.name}: {entry['state']} - {entry['note']}")
    data_dir.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--only", default="", help="쉼표로 구분한 수집원 이름 (비우면 전부)")
    args = parser.parse_args()
    status = run(Settings().data_dir, args.year, [s.strip() for s in args.only.split(",") if s.strip()] or None)
    # 경기 기록을 못 받았으면 뒤 단계(브리핑·배포)를 돌릴 이유가 없으므로 실패로 알린다.
    return 1 if status.get("leaguepedia", {}).get("state") == "실패" else 0


if __name__ == "__main__":
    sys.exit(main())
