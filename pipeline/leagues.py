"""리그 단위 집계: 현재 시리즈의 일정, 스테이지별 팀 전적, 주요 경기 점수."""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .pandascore import pick_current_serie
from .schemas import LeagueFeed, LeagueRecord, Match, StageRecord, Standing, Team

INTERNATIONAL = ("worlds", "world championship", "mid-season", "msi", "first stand", "월즈", "퍼스트 스탠드")
FINAL_WORDS = ("final", "결승")
# "quarterfinal", "semifinal" 에도 final 이 들어 있어 결승보다 먼저 걸러 낸다.
PRE_FINAL_WORDS = ("quarter", "semi", "8강", "4강", "준결승")
KNOCKOUT_WORDS = (
    "playoff", "play-off", "play-in", "knockout", "bracket", "플레이오프", "플레이-인", "토너먼트", "브래킷", "선발전",
)

# (A팀 순위, B팀 순위, 전적표의 팀 수)
Ranker = Callable[[Match], tuple[int | None, int | None, int]]


def _standings(matches: list[Match]) -> list[Standing]:
    table: dict[int, Standing] = {}
    for m in sorted(matches, key=lambda m: m.end_at or m.begin_at or "", reverse=True):
        if m.status != "finished" or m.winner_id is None:
            continue
        for team, mine, theirs in ((m.team_a, m.score_a, m.score_b), (m.team_b, m.score_b, m.score_a)):
            row = table.setdefault(team.id, Standing(team=team))
            won = m.winner_id == team.id
            row.wins += won
            row.losses += not won
            row.set_wins += mine
            row.set_losses += theirs
            if len(row.recent) < 5:
                row.recent.append(won)
    for row in table.values():
        first = row.recent[0] if row.recent else None
        run = 0
        for won in row.recent:
            if won != first:
                break
            run += 1
        row.streak = run if first else -run
    # 승수 → 세트 득실 순. 공식 순위는 상대 전적 등 추가 기준을 쓰므로 다를 수 있다.
    return sorted(
        table.values(),
        key=lambda r: (-r.wins, -(r.set_wins - r.set_losses), r.losses, r.team.name),
    )


def build_league(feed: LeagueFeed) -> LeagueRecord:
    serie_id = pick_current_serie(feed.matches)
    current = [m for m in feed.matches if m.serie_id == serie_id and m.status in ("finished", "running", "not_started")]
    current.sort(key=lambda m: m.begin_at or "")

    by_stage: dict[str, list[Match]] = defaultdict(list)
    for m in current:
        by_stage[m.tournament or "전체"].append(m)
    # 가장 최근에 경기가 있었던 스테이지가 먼저 오게 한다.
    stages = [
        StageRecord(name=name, standings=_standings(ms))
        for name, ms in sorted(
            by_stage.items(),
            # 최근 스테이지가 먼저. 같은 기간에 열린 그룹은 레전드 그룹을 앞에 둔다.
            key=lambda kv: (max((m.begin_at or "")[:10] for m in kv[1]), "라이즈" not in kv[0]),
            reverse=True,
        )
    ]
    stages = [s for s in stages if s.standings]
    # 누적 순위표는 기준이 되는 스테이지 바로 앞에 끼워 넣는다.
    for table in feed.tables:
        members = {t.id for m in by_stage.get(table.teams_from, []) for t in (m.team_a, m.team_b)}
        pool = [m for name in table.stages for m in by_stage.get(name, [])]
        rows = [row for row in _standings(pool) if row.team.id in members]
        if not rows:
            continue
        at = next((i for i, st in enumerate(stages) if st.name == table.teams_from), len(stages))
        stages.insert(at, StageRecord(name=table.name, standings=rows))

    has_finished = any(m.status == "finished" for m in current)
    has_pending = any(m.status in ("running", "not_started") for m in current)
    status = "진행 중" if has_pending and (has_finished or any(m.status == "running" for m in current)) else (
        "시작 전" if has_pending else "종료"
    )
    serie_name = feed.serie or next((m.stage.removesuffix(m.tournament).strip() for m in current if m.stage), "")
    return LeagueRecord(id=feed.id, name=feed.name, serie=serie_name, status=status, stages=stages, matches=current)


def make_ranker(leagues: list[LeagueRecord]) -> Ranker:
    """경기의 두 팀이 해당 스테이지 전적표에서 몇 위인지 돌려주는 함수를 만든다."""
    ranks: dict[tuple[int | None, str], dict[int, int]] = {}
    for league in leagues:
        for stage in league.stages:
            ranks[(league.id, stage.name)] = {row.team.id: i for i, row in enumerate(stage.standings, 1)}

    def rank(match: Match) -> tuple[int | None, int | None, int]:
        table = ranks.get((match.league_id, match.tournament or "전체"), {})
        return table.get(match.team_a.id), table.get(match.team_b.id), len(table)

    return rank


def importance(match: Match, tags: list[str], ranks: tuple[int | None, int | None, int]) -> tuple[int, list[str]]:
    """주요 경기 점수와 그 이유. 규칙 기반이라 같은 입력이면 항상 같은 결과가 나온다."""
    score, reasons = 0, []
    stage = f"{match.stage} {match.tournament}".lower()
    bracket = True
    if any(w in stage for w in PRE_FINAL_WORDS):
        score += 3
        reasons.append("4강" if any(w in stage for w in ("semi", "4강", "준결승")) else "8강")
    elif any(w in stage for w in FINAL_WORDS):
        score += 4
        reasons.append("결승")
    elif any(w in stage for w in KNOCKOUT_WORDS):
        score += 3
        reasons.append("플레이오프")
    else:
        bracket = "스위스" in stage or "swiss" in stage
    if any(w in match.league.lower() for w in INTERNATIONAL):
        score += 3
        reasons.append("국제 대회")
    # 순위 맞대결은 풀리그 스테이지에서만 의미가 있다. 토너먼트의 승패 표는 순위가 아니다.
    a, b, size = (None, None, 0) if bracket else ranks
    if a and b and max(a, b) <= 2 and size >= 4:
        score += 3
        reasons.append("1·2위 맞대결")
    elif a and b and max(a, b) <= 4 and size >= 8:
        score += 2
        reasons.append("상위권 맞대결")
    if match.best_of >= 5:
        score += 1  # 점수에만 반영한다. 전제는 화면에 따로 표시된다.
    for tag, points in (("이변", 2), ("역스윕", 2), ("풀세트", 1), ("연승 저지", 1)):
        if tag in tags:
            score += points
            reasons.append(tag)
    return score, reasons


def team_of(leagues: list[LeagueRecord], team_id: int) -> Team | None:
    for league in leagues:
        for m in league.matches:
            for t in (m.team_a, m.team_b):
                if t.id == team_id:
                    return t
    return None
