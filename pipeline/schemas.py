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
    league_id: int | None = None
    serie_id: int | None = None
    tournament: str = ""
    # 스테이지 안에서의 라운드(8강, 4강, 결승, 1라운드 ...). 대진표를 그릴 때 쓴다.
    round: str = ""
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
    # 경기 전 최근 전적(최신순, True=승). 화면의 승/패 표시용.
    recent_a: list[bool] = Field(default_factory=list)
    recent_b: list[bool] = Field(default_factory=list)
    headline: str
    summary: list[str]
    tags: list[str]
    facts: list[str]
    # 주요 경기 선정용 점수와 그 이유(편집 단계에서 채운다).
    importance: int = 0
    reasons: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "template"]
    trace: list[TraceStep]


class PreviewRecord(BaseModel):
    match: Match
    recent_a: list[bool] = Field(default_factory=list)
    recent_b: list[bool] = Field(default_factory=list)
    form_a: str
    form_b: str
    h2h: str
    case_a: list[str]
    case_b: list[str]
    watch_points: list[str]
    importance: int = 0
    reasons: list[str] = Field(default_factory=list)
    generated_by: Literal["llm", "template"]
    trace: list[TraceStep]


# ---- 리그 일정·전적 ----


class CombinedTable(BaseModel):
    """여러 스테이지의 경기를 합쳐 만드는 순위표(예: 정규 시즌 누적)."""

    name: str
    stages: list[str]
    # 이 스테이지에 나온 팀만 표에 넣는다.
    teams_from: str


class LeagueFeed(BaseModel):
    """데이터 소스가 돌려주는 리그 한 곳의 경기 묶음(종료·진행 중·예정 모두 포함)."""

    id: int
    name: str
    # 시리즈 이름을 소스가 알고 있으면 채운다. 비어 있으면 경기의 stage 에서 추정한다.
    serie: str = ""
    matches: list[Match]
    tables: list[CombinedTable] = Field(default_factory=list)


class Standing(BaseModel):
    team: Team
    wins: int = 0
    losses: int = 0
    set_wins: int = 0
    set_losses: int = 0
    recent: list[bool] = Field(default_factory=list)  # 최신순, True=승
    streak: int = 0  # 양수 연승, 음수 연패


class StageRecord(BaseModel):
    name: str
    standings: list[Standing]


class BracketSlot(BaseModel):
    match_id: int
    # 이 경기로 정해진 각 팀의 결과: "", "진출", "탈락", "우승", "준우승"
    note_a: str = ""
    note_b: str = ""


class BracketRound(BaseModel):
    name: str
    slots: list[BracketSlot]


class Bracket(BaseModel):
    stage: str
    # True 면 한 번 지면 탈락하는 토너먼트라 가지 모양으로 이어 그릴 수 있다.
    tree: bool
    rounds: list[BracketRound]


class LeagueRecord(BaseModel):
    id: int
    name: str
    serie: str
    status: Literal["진행 중", "시작 전", "종료"]
    stages: list[StageRecord]
    matches: list[Match]
    brackets: list[Bracket] = Field(default_factory=list)
