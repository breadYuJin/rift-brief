"""파이프라인 전체가 공유하는 데이터 모델."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Team(BaseModel):
    id: int
    name: str
    acronym: str


class Game(BaseModel):
    position: int
    winner_id: int | None = None
    length_min: int | None = None


class Match(BaseModel):
    """PandaScore 매치를 사이트에 필요한 필드만 남겨 정규화한 형태."""

    id: int
    league: str
    stage: str
    best_of: int
    status: str
    begin_at: str | None = None
    end_at: str | None = None
    team_a: Team
    team_b: Team
    score_a: int = 0
    score_b: int = 0
    winner_id: int | None = None
    games: list[Game] = Field(default_factory=list)

    @property
    def winner(self) -> Team | None:
        if self.winner_id == self.team_a.id:
            return self.team_a
        if self.winner_id == self.team_b.id:
            return self.team_b
        return None

    @property
    def loser(self) -> Team | None:
        w = self.winner
        if w is None:
            return None
        return self.team_b if w.id == self.team_a.id else self.team_a


class FormEntry(BaseModel):
    opponent: str
    won: bool
    score: str
    date: str | None = None


class TeamForm(BaseModel):
    team_id: int
    recent: list[FormEntry] = Field(default_factory=list)

    @property
    def wins(self) -> int:
        return sum(1 for e in self.recent if e.won)

    @property
    def losses(self) -> int:
        return len(self.recent) - self.wins

    @property
    def streak(self) -> int:
        """양수면 연승, 음수면 연패."""
        if not self.recent:
            return 0
        first = self.recent[0].won
        n = 0
        for e in self.recent:
            if e.won != first:
                break
            n += 1
        return n if first else -n


class Context(BaseModel):
    """수집 에이전트가 모은, 해당 경기 이전 시점의 배경 정보."""

    form_a: TeamForm
    form_b: TeamForm
    h2h_a_wins: int = 0
    h2h_b_wins: int = 0


# ---- LLM 구조화 출력 스키마 ----


class Analysis(BaseModel):
    angle: str = Field(description="이 경기를 한 문장으로 규정하는 핵심 관점")
    key_points: list[str] = Field(description="팩트 목록에서 고른 핵심 포인트 2~3개", max_length=3)


class Draft(BaseModel):
    headline: str = Field(description="28자 이내 한국어 헤드라인")
    summary: list[str] = Field(description="각 60자 이내 한국어 문장 3개", min_length=3, max_length=3)


class Review(BaseModel):
    ok: bool = Field(description="모든 주장이 팩트 목록으로 뒷받침되면 true")
    issues: list[str] = Field(default_factory=list, description="팩트에 없는 주장이나 오류")


class Case(BaseModel):
    points: list[str] = Field(description="이 팀이 유리하다고 볼 근거 2개", min_length=1, max_length=2)


class WatchPoints(BaseModel):
    points: list[str] = Field(description="중립적인 관전 포인트 2~3개", min_length=2, max_length=3)


# ---- 사이트로 내보내는 레코드 ----


class TraceStep(BaseModel):
    agent: str
    note: str


class BriefRecord(BaseModel):
    match: Match
    headline: str
    summary: list[str]
    tags: list[str]
    facts: list[str]
    generated_by: Literal["llm", "template"]
    trace: list[TraceStep]


class PreviewRecord(BaseModel):
    match: Match
    form_a: str
    form_b: str
    h2h: str
    case_a: list[str]
    case_b: list[str]
    watch_points: list[str]
    generated_by: Literal["llm", "template"]
    trace: list[TraceStep]
