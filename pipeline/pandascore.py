"""PandaScore REST 클라이언트 (무료 Fixtures 플랜 범위: 일정·결과·팀)."""
from __future__ import annotations

import time
from typing import Any

import requests

from .schemas import FormEntry, Game, Match, Team, TeamForm

BASE_URL = "https://api.pandascore.co"


def normalize_match(raw: dict[str, Any]) -> Match | None:
    """상대가 확정되지 않은 경기(TBD)는 None."""
    opponents = [o.get("opponent") or {} for o in raw.get("opponents") or []]
    if len(opponents) != 2 or not all(o.get("id") for o in opponents):
        return None
    a, b = (
        Team(id=o["id"], name=o.get("name") or "?", acronym=o.get("acronym") or o.get("name") or "?")
        for o in opponents
    )
    scores = {r.get("team_id"): r.get("score") or 0 for r in raw.get("results") or []}
    games = []
    for g in sorted(raw.get("games") or [], key=lambda g: g.get("position") or 0):
        if not g.get("finished") and g.get("status") != "finished":
            continue
        length = g.get("length")
        games.append(
            Game(
                position=g.get("position") or len(games) + 1,
                winner_id=(g.get("winner") or {}).get("id"),
                length_min=round(length / 60) if length else None,
            )
        )
    serie = (raw.get("serie") or {}).get("full_name") or ""
    tournament = (raw.get("tournament") or {}).get("name") or ""
    return Match(
        id=raw["id"],
        league=(raw.get("league") or {}).get("name") or "LoL",
        stage=" ".join(p for p in (serie, tournament) if p),
        league_id=(raw.get("league") or {}).get("id") or raw.get("league_id"),
        serie_id=raw.get("serie_id") or (raw.get("serie") or {}).get("id"),
        tournament=tournament,
        best_of=raw.get("number_of_games") or 1,
        status=raw.get("status") or "",
        begin_at=raw.get("begin_at") or raw.get("scheduled_at"),
        end_at=raw.get("end_at"),
        team_a=a,
        team_b=b,
        score_a=scores.get(a.id, 0),
        score_b=scores.get(b.id, 0),
        winner_id=raw.get("winner_id"),
        games=games,
    )


def form_from_matches(team_id: int, matches: list[Match], before: str | None, size: int = 5) -> TeamForm:
    """팀의 최근 전적. `before` 이전에 끝난 경기만 센다(브리핑 대상 경기 자체는 제외)."""
    entries: list[FormEntry] = []
    for m in sorted(matches, key=lambda m: m.end_at or "", reverse=True):
        if m.winner_id is None or (before and (m.end_at or "") >= before):
            continue
        mine_is_a = m.team_a.id == team_id
        opp = m.team_b if mine_is_a else m.team_a
        mine, theirs = (m.score_a, m.score_b) if mine_is_a else (m.score_b, m.score_a)
        entries.append(
            FormEntry(opponent=opp.acronym, won=m.winner_id == team_id, score=f"{mine}-{theirs}", date=m.end_at)
        )
        if len(entries) == size:
            break
    return TeamForm(team_id=team_id, recent=entries)


def pick_current_serie(matches: list[Match]) -> int | None:
    """아직 안 끝난 경기 중 가장 이른 것의 시리즈. 없으면 가장 최근에 끝난 경기의 시리즈."""
    pending = [m for m in matches if m.status in ("running", "not_started") and m.begin_at]
    if pending:
        return min(pending, key=lambda m: m.begin_at or "").serie_id
    finished = [m for m in matches if m.status == "finished"]
    if finished:
        return max(finished, key=lambda m: m.end_at or m.begin_at or "").serie_id
    return None


class PandaScoreClient:
    def __init__(self, token: str, session: requests.Session | None = None):
        self._session = session or requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})
        self._team_cache: dict[int, list[Match]] = {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(3):
            resp = self._session.get(f"{BASE_URL}{path}", params=params, timeout=20)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return []

    def league_name(self, league_id: int) -> str:
        try:
            return self._get(f"/leagues/{league_id}").get("name") or str(league_id)
        except requests.RequestException:
            return str(league_id)

    def resolve_leagues(self, names: list[str]) -> list[tuple[int, str]]:
        ids: list[tuple[int, str]] = []
        for name in names:
            found = self._get("/lol/leagues", {"search[name]": name, "page[size]": 20})
            exact = [l for l in found if (l.get("name") or "").lower() == name.lower()]
            pick = (exact or found or [None])[0]
            if pick:
                ids.append((pick["id"], pick.get("name") or name))
                print(f"[pandascore] 리그 '{name}' → {pick.get('name')} (id={pick['id']})")
            else:
                print(f"[pandascore] 리그 '{name}' 를 찾지 못함")
        return ids

    def league_matches(self, league_id: int, max_pages: int = 3) -> list[Match]:
        """리그의 경기를 최신순으로 받는다. 현재 시리즈가 다음 페이지로 이어지는 동안만 더 읽는다."""
        found: list[Match] = []
        current_serie: int | None = None
        for page in range(1, max_pages + 1):
            raw = self._get(
                f"/leagues/{league_id}/matches",
                {"sort": "-begin_at", "page[size]": 100, "page[number]": page},
            )
            found += [m for m in (normalize_match(r) for r in raw) if m]
            if current_serie is None:
                current_serie = pick_current_serie(found)
            last_serie = raw[-1].get("serie_id") if raw else None
            if len(raw) < 100 or last_serie != current_serie:
                break
        return found

    def team_matches(self, team_id: int) -> list[Match]:
        """팀의 최근 종료 경기. 실패해도 브리핑은 계속되도록 빈 목록을 돌려준다."""
        if team_id not in self._team_cache:
            try:
                raw = self._get(
                    f"/teams/{team_id}/matches",
                    {"filter[status]": "finished", "sort": "-end_at", "page[size]": 20},
                )
                self._team_cache[team_id] = [m for m in (normalize_match(r) for r in raw) if m]
            except requests.RequestException as exc:
                print(f"[pandascore] 팀 {team_id} 전적 조회 실패: {exc}")
                self._team_cache[team_id] = []
        return self._team_cache[team_id]
