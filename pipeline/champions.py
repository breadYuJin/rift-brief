"""챔피언 한국어 이름표: `python -m pipeline.champions`

Riot 의 공개 정적 데이터(Data Dragon)에서 최신 패치의 챔피언 목록을 받아 data/champions.json 에 저장한다.
수집한 경기 기록은 챔피언을 영어 이름으로 적으므로, 사이트는 이 표로 한국어 이름을 찾는다.
받지 못하면 기존 파일을 그대로 둔다(사이트는 영어 이름을 보여 준다).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from .config import Settings

BASE = "https://ddragon.leagueoflegends.com"
# 기록에 쓰이는 이름이 공식 이름과 다른 경우: 기록의 이름 → 공식 영어 이름
ALIASES = {"Nunu": "Nunu & Willump", "Renata": "Renata Glasc"}


def key(name: str) -> str:
    """이름 비교용 키: 소문자 영문·숫자만 남긴다. (K'Sante → ksante)"""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_table(version: str, english: dict[str, Any], korean: dict[str, Any]) -> dict[str, Any]:
    champions: dict[str, dict[str, str]] = {}
    for champ_id, en in english["data"].items():
        ko = korean["data"].get(champ_id, {})
        entry = {"id": champ_id, "en": en["name"], "ko": ko.get("name") or en["name"]}
        champions[key(en["name"])] = entry
        champions.setdefault(key(champ_id), entry)  # 예: Wukong 의 내부 이름 MonkeyKing
    for alias, official in ALIASES.items():
        if key(official) in champions:
            champions.setdefault(key(alias), champions[key(official)])
    return {
        "version": version,
        # 챔피언 얼굴 아이콘 주소는 icon_base + <id>.png
        "icon_base": f"{BASE}/cdn/{version}/img/champion/",
        "champions": dict(sorted(champions.items())),
    }


def _get_json(url: str) -> Any:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch(get: Callable[[str], Any] = _get_json) -> dict[str, Any]:
    version = get(f"{BASE}/api/versions.json")[0]
    english = get(f"{BASE}/cdn/{version}/data/en_US/champion.json")
    korean = get(f"{BASE}/cdn/{version}/data/ko_KR/champion.json")
    return build_table(version, english, korean)


def save(data_dir: Path, table: dict[str, Any]) -> None:
    path = data_dir / "champions.json"
    text = json.dumps(table, ensure_ascii=False, indent=1) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def namer(data_dir: Path) -> Callable[[str], str]:
    """기록의 영어 이름을 한국어 이름으로 바꾸는 함수. 이름표가 없으면 이름을 그대로 돌려준다."""
    try:
        table = json.loads((data_dir / "champions.json").read_text(encoding="utf-8"))["champions"]
    except (OSError, ValueError, KeyError):
        return str
    return lambda english: table.get(key(english), {}).get("ko", english)


def main() -> int:
    try:
        table = fetch()
    except Exception as exc:
        print(f"[챔피언] 받지 못함, 기존 파일 유지: {exc}")
        return 0
    save(Path(Settings().data_dir), table)
    print(f"[챔피언] 패치 {table['version']}, {len({c['id'] for c in table['champions'].values()})}명")
    return 0


if __name__ == "__main__":
    sys.exit(main())
