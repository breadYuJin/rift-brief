"""PANDASCORE_TOKEN 이 없을 때 쓰는 샘플 데이터 소스.

실제 팀의 가짜 결과가 사이트에 올라가지 않도록 전부 가상의 팀이다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .schemas import Game, LeagueFeed, Match, Team

LEAGUE_ID = 1
SERIE_ID = 10
TEAMS = {
    1: Team(id=1, name="샘플 타이거즈", acronym="STG"),
    2: Team(id=2, name="데모 드래곤즈", acronym="DDR"),
    3: Team(id=3, name="목업 유나이티드", acronym="MKU"),
    4: Team(id=4, name="테스트 피닉스", acronym="TPX"),
}

# (며칠 전, 팀A, 팀B, 세트별 승자, 세트 길이(분))
_PAST = [
    (1, 1, 2, [2, 1, 1], [34, 29, 41]),
    (1, 3, 4, [3, 3], [27, 31]),
    (2, 2, 4, [2, 4, 2], [30, 38, 33]),
    (3, 1, 3, [1, 1], [25, 28]),
    (4, 4, 1, [4, 4, 1, 1, 1], [31, 36, 29, 33, 44]),
    (5, 2, 3, [3, 3], [32, 26]),
    (6, 1, 4, [1, 1], [28, 30]),
    (7, 3, 2, [3, 2, 3], [35, 31, 37]),
    (8, 1, 2, [1, 2, 1], [33, 30, 29]),
    (9, 4, 3, [3, 3], [26, 34]),
]
# (며칠 뒤, 팀A, 팀B, 스테이지, 전제)
_UPCOMING = [
    (1, 2, 4, "정규 시즌", 3),
    (2, 3, 4, "정규 시즌", 3),
    (4, 1, 3, "플레이오프 결승", 5),
]


class SampleSource:
    def __init__(self, now: datetime | None = None):
        # 날짜 단위로 고정해 같은 날 여러 번 돌려도 결과가 같게 한다.
        self._now = (now or datetime.now(timezone.utc)).replace(hour=9, minute=0, second=0, microsecond=0)
        self._past = [self._finished(i, *row) for i, row in enumerate(_PAST)]

    def _match(self, **kw) -> Match:
        tournament = kw.pop("tournament", "정규 시즌")
        return Match(
            league="샘플 리그",
            league_id=LEAGUE_ID,
            serie_id=SERIE_ID,
            tournament=tournament,
            stage=f"시범 시즌 {tournament}",
            **kw,
        )

    def _finished(self, idx: int, days_ago: int, a: int, b: int, winners: list[int], lengths: list[int]) -> Match:
        end = self._now - timedelta(days=days_ago, hours=idx % 2 * 2)
        score_a, score_b = winners.count(a), winners.count(b)
        best_of = 5 if len(winners) > 3 or max(score_a, score_b) == 3 else 3
        return self._match(
            id=9000 + idx,
            best_of=best_of,
            status="finished",
            begin_at=(end - timedelta(hours=2)).isoformat(),
            end_at=end.isoformat(),
            team_a=TEAMS[a],
            team_b=TEAMS[b],
            score_a=score_a,
            score_b=score_b,
            winner_id=a if score_a > score_b else b,
            games=[Game(position=i + 1, winner_id=w, length_min=l) for i, (w, l) in enumerate(zip(winners, lengths))],
        )

    def past_matches(self) -> list[Match]:
        return self._past[:6]

    def upcoming_matches(self) -> list[Match]:
        return [
            self._match(
                id=9500 + i,
                tournament=stage,
                best_of=best_of,
                status="not_started",
                begin_at=(self._now + timedelta(days=days, hours=i * 2)).isoformat(),
                team_a=TEAMS[a],
                team_b=TEAMS[b],
            )
            for i, (days, a, b, stage, best_of) in enumerate(_UPCOMING)
        ]

    def running_match(self) -> Match:
        """화면 확인용으로 진행 중인 경기 하나를 둔다(1세트 종료 시점)."""
        return self._match(
            id=9400,
            best_of=3,
            status="running",
            begin_at=self._now.isoformat(),
            team_a=TEAMS[1],
            team_b=TEAMS[3],
            score_a=1,
            score_b=0,
            games=[Game(position=1, winner_id=1, length_min=31)],
        )

    def leagues(self) -> list[LeagueFeed]:
        matches = [*self._past, self.running_match(), *self.upcoming_matches()]
        return [LeagueFeed(id=LEAGUE_ID, name="샘플 리그", matches=matches)]

    def team_matches(self, team_id: int) -> list[Match]:
        return [m for m in self._past if team_id in (m.team_a.id, m.team_b.id)]
