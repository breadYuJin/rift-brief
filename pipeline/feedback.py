"""평점에 대한 팬 의견 받기.

사이트의 "의견 보내기"를 누르면 이 저장소의 GitHub 이슈 작성 화면이 열린다(주소는 web/lib/feedback.ts 가
만든다). 제목은 "[평점]" 으로 시작하고 본문은 아래 모양이다. 수집 때 이런 이슈를 읽어 선수·세트별로 의견을 모은다.

    경기: 2856364077
    세트: 2

    Bin: 7.5
    Chovy: 6

규칙
  - 한 계정이 같은 선수·같은 세트에 여러 번 보내면 마지막 것만 센다.
  - 그 세트에 뛰지 않은 선수, 1~10 을 벗어난 점수, 숫자가 없는 줄은 버린다.
  - 계정 이름은 저장하지 않고 알아볼 수 없게 바꾼 값만 남긴다.
  - 평점에 얼마나 섞을지는 ratings.blend 와 ratings.config.json 이 정한다(기본: 3명부터, 최대 30%, ±1점).

GITHUB_TOKEN 과 GITHUB_REPOSITORY 가 있어야 돈다(GitHub Actions 에서는 자동으로 주어진다).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from .gamedata import SetRecord

TITLE_PREFIX = "[평점]"
API = "https://api.github.com"
MAX_PAGES = 20
_LINE = re.compile(r"^\s*[-*]?\s*(.+?)\s*[:：=]\s*(\d{1,2}(?:[.,]\d+)?)\s*점?\s*$")
_MATCH = re.compile(r"^\s*경기\s*[:：]\s*(\d+)\s*$", re.M)
_SET = re.compile(r"^\s*세트\s*[:：]\s*(\d+)\s*$", re.M)

Get = Callable[[str, dict[str, Any]], Any]


def _http_get(path: str, params: dict[str, Any]) -> Any:
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
    r = requests.get(f"{API}{path}", params=params, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def voter_id(login: str) -> str:
    return hashlib.sha1(f"rift-brief:{login.lower()}".encode()).hexdigest()[:12]


def parse_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    """이슈 하나를 의견 한 건으로 바꾼다. 평점 의견이 아니거나 읽을 수 없으면 None."""
    title, body = issue.get("title") or "", issue.get("body") or ""
    if "pull_request" in issue or not title.strip().startswith(TITLE_PREFIX):
        return None
    match, number = _MATCH.search(body), _SET.search(body)
    if not match or not number:
        return None
    scores: dict[str, float] = {}
    for line in body.splitlines():
        m = _LINE.match(line)
        if not m or m.group(1) in ("경기", "세트"):
            continue
        score = float(m.group(2).replace(",", "."))
        if 1.0 <= score <= 10.0:
            scores[m.group(1).strip()] = score
    if not scores:
        return None
    return {
        "issue": issue.get("number"),
        "voter": voter_id((issue.get("user") or {}).get("login") or "?"),
        "at": issue.get("created_at") or "",
        "match_id": int(match.group(1)),
        "set": int(number.group(1)),
        "scores": scores,
    }


def fetch_votes(repo: str, get: Get = _http_get) -> list[dict[str, Any]]:
    votes = []
    for page in range(1, MAX_PAGES + 1):
        issues = get(
            f"/repos/{repo}/issues",
            {"state": "all", "per_page": 100, "page": page, "sort": "created", "direction": "asc"},
        )
        votes += [v for v in map(parse_issue, issues) if v]
        if len(issues) < 100:
            break
    return votes


def collect(data_dir: Path, year: int, get: Get = _http_get) -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "")
    if not repo:
        return "건너뜀: GITHUB_REPOSITORY 없음"
    votes = fetch_votes(repo, get)
    path = data_dir / "raw" / "rating_votes.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(votes, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return f"평점 의견 {len(votes)}건 ({len({v['voter'] for v in votes})}명)"


def load_votes(data_dir: Path) -> list[dict[str, Any]]:
    try:
        return json.loads((data_dir / "raw" / "rating_votes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def aggregate(
    votes: list[dict[str, Any]], sets: list[SetRecord]
) -> dict[str, dict[tuple[int, str], tuple[float, int]]]:
    """세트 ID → (팀 ID, 선수) → (의견 평균, 의견 수). 그 세트에 뛴 선수에 대한 의견만 센다."""
    by_key = {(s.match_id, s.number): s for s in sets}
    latest: dict[tuple[str, str, int, str], float] = {}
    for v in sorted(votes, key=lambda v: (v.get("at") or "", v.get("issue") or 0)):
        s = by_key.get((v.get("match_id"), v.get("set")))
        if not s:
            continue
        names = {p.player.lower(): (p.team_id, p.player) for p in s.players}
        for name, score in (v.get("scores") or {}).items():
            # "BLG Bin" 처럼 팀 약칭을 앞에 붙여 적어도 알아듣는다.
            key = names.get(name.lower()) or names.get(name.split()[-1].lower())
            if key and isinstance(score, (int, float)) and 1.0 <= score <= 10.0:
                latest[(v["voter"], s.game_id, key[0], key[1])] = float(score)
    grouped: dict[str, dict[tuple[int, str], list[float]]] = defaultdict(lambda: defaultdict(list))
    for (_voter, game_id, team_id, player), score in latest.items():
        grouped[game_id][(team_id, player)].append(score)
    return {g: {k: (sum(xs) / len(xs), len(xs)) for k, xs in players.items()} for g, players in grouped.items()}


def digest(votes: list[dict[str, Any]]) -> str:
    return hashlib.sha1(json.dumps(votes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]
