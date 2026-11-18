"""실시간 밴픽 추적의 뼈대.

밴픽이 한 수 진행될 때마다 남은 칸의 예상을 다시 낸다. 지금은 입력을 직접 넣는 ManualFeed 만 있고,
실시간 데이터(GRID 등)가 확보되면 같은 모양의 이벤트를 내는 피드를 하나 더 만들어 끼우면 된다.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from typing import Any, Protocol

from pydantic import BaseModel

from .draft_model import DraftModel
from .gamedata import DRAFT_ORDER, SetRecord
from .schemas import Team


class DraftEvent(BaseModel):
    """밴픽 한 수. 순서는 표준 밴픽 순서를 따른다고 본다."""

    kind: str  # "ban" 또는 "pick"
    team_id: int
    champion: str


class DraftFeed(Protocol):
    """한 세트의 밴픽을 순서대로 내놓는 입력원."""

    def events(self) -> Iterator[DraftEvent]: ...


class ManualFeed:
    """사람이 넣었거나 지난 기록에서 가져온 밴픽을 순서대로 내놓는다."""

    def __init__(self, events: Iterable[DraftEvent]):
        self._events = list(events)

    @classmethod
    def from_set(cls, s: SetRecord) -> ManualFeed:
        return cls(DraftEvent(kind=step.kind, team_id=step.team_id, champion=step.champion) for step in s.draft)

    def events(self) -> Iterator[DraftEvent]:
        return iter(self._events)


class GridFeed:
    """GRID 실시간 밴픽 피드 자리. 접근 권한이 생기면 여기를 구현한다.

    필요한 것: GRID_API_KEY, 시리즈 ID. GRID 의 시리즈 상태(챔피언 선택 단계)를 구독해
    밴·픽이 확정될 때마다 DraftEvent 를 내보내면 나머지(track)는 그대로 쓸 수 있다.
    """

    def __init__(self, series_id: str, api_key: str | None = None):
        self.series_id = series_id
        self.api_key = api_key or os.getenv("GRID_API_KEY", "")

    def events(self) -> Iterator[DraftEvent]:
        raise NotImplementedError(
            "GRID 연결은 아직 구현되지 않았습니다. GRID 의 LoL 데이터 접근 권한을 받은 뒤 "
            "pipeline/live.py 의 GridFeed.events 를 구현하세요."
        )


def track(
    feed: DraftFeed,
    model: DraftModel,
    first: Team,
    second: Team,
    patch: str | None = None,
    unavailable: set[str] | None = None,
    top: int = 5,
) -> Iterator[dict[str, Any]]:
    """밴픽이 한 수 들어올 때마다 '다음 차례 팀이 무엇을 할지' 예상을 낸다.

    첫 결과는 아무것도 두지 않은 시점의 예상이다.
    """
    taken = set(unavailable or ())
    teams = {"F": first, "S": second}
    done = 0

    def forecast() -> dict[str, Any] | None:
        if done >= len(DRAFT_ORDER):
            return None
        kind, who, _ = DRAFT_ORDER[done]
        team, opp = teams[who], teams["S" if who == "F" else "F"]
        p = model.predict(team.id, opp.id, patch, unavailable=taken, top=top)
        return {"step": done + 1, "kind": kind, "team_id": team.id, "candidates": p.bans if kind == "ban" else p.picks}

    first_view = forecast()
    if first_view:
        yield first_view
    for event in feed.events():
        taken.add(event.champion)
        done += 1
        view = forecast()
        if view:
            yield {**view, "after": event.model_dump()}
