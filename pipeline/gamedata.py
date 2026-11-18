"""세트 단위 기록: 밴픽 순서, 진영, 오브젝트·킬·골드, 선수 기록, 타임라인.

수집해 둔 원본(data/raw/)을 모델과 에이전트가 쓰는 형태로 정리한다. 네트워크를 쓰지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .leaguepedia import LEAGUES, official_player, resolve_team, stable_id
from .schemas import Team

# 표준 밴픽 순서. F 는 먼저 밴픽하는 팀, S 는 나중 팀. (종류, 팀, 그 팀의 몇 번째인지)
DRAFT_ORDER: list[tuple[str, str, int]] = (
    [("ban", t, i) for i in (1, 2, 3) for t in ("F", "S")]
    + [("pick", "F", 1), ("pick", "S", 1), ("pick", "S", 2), ("pick", "F", 2), ("pick", "F", 3), ("pick", "S", 3)]
    + [("ban", "S", 4), ("ban", "F", 4), ("ban", "S", 5), ("ban", "F", 5)]
    + [("pick", "S", 4), ("pick", "F", 4), ("pick", "F", 5), ("pick", "S", 5)]
)
ROLES = ["탑", "정글", "미드", "원딜", "서포터"]
_ROLE_ALIASES = {
    "top": "탑",
    "jungle": "정글",
    "mid": "미드",
    "bot": "원딜",
    "adc": "원딜",
    "support": "서포터",
}


def role_name(raw: str | None) -> str:
    return _ROLE_ALIASES.get((raw or "").strip().lower(), "")


class DraftStep(BaseModel):
    kind: Literal["ban", "pick"]
    team_id: int
    champion: str
    role: str = ""


class TeamStats(BaseModel):
    kills: int = 0
    gold: int = 0
    dragons: int = 0
    barons: int = 0
    towers: int = 0
    heralds: int = 0
    grubs: int = 0
    atakhans: int = 0
    inhibitors: int = 0


class PlayerLine(BaseModel):
    team_id: int
    player: str
    champion: str
    role: str
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    cs: int = 0
    gold: int = 0
    damage: int = 0
    vision: int = 0


class SetRecord(BaseModel):
    game_id: str
    match_id: int
    league: str
    number: int
    start: str = ""
    patch: str = ""
    blue: Team
    red: Team
    winner_id: int | None = None
    length_min: float | None = None
    first_pick_id: int | None = None
    draft: list[DraftStep] = Field(default_factory=list)
    blue_stats: TeamStats = Field(default_factory=TeamStats)
    red_stats: TeamStats = Field(default_factory=TeamStats)
    players: list[PlayerLine] = Field(default_factory=list)
    rpg: str = ""
    vod: str = ""
    official_mvp: str | None = None  # 주최 측이 세트마다 뽑는 대회에서의 세트 MVP

    def team(self, team_id: int) -> Team:
        return self.blue if team_id == self.blue.id else self.red

    def other(self, team_id: int) -> Team:
        return self.red if team_id == self.blue.id else self.blue

    def champions(self, team_id: int, kind: str) -> list[str]:
        return [s.champion for s in self.draft if s.team_id == team_id and s.kind == kind]

    @property
    def picked(self) -> list[str]:
        return [s.champion for s in self.draft if s.kind == "pick"]


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _iso(value: str | None) -> str:
    return (value or "").replace(" ", "T") + ("+00:00" if value else "")


def _draft(row: dict[str, Any], first: Team, second: Team) -> list[DraftStep]:
    steps: list[DraftStep] = []
    for kind, who, i in DRAFT_ORDER:
        col = "Team1" if who == "F" else "Team2"
        champion = (row.get(f"{col}{'Ban' if kind == 'ban' else 'Pick'}{i}") or "").strip()
        if not champion or champion.lower() in ("none", "missing data", "loss of ban"):
            continue
        steps.append(
            DraftStep(
                kind=kind,  # type: ignore[arg-type]
                team_id=(first if who == "F" else second).id,
                champion=champion,
                role=role_name(row.get(f"{col}Role{i}")) if kind == "pick" else "",
            )
        )
    return steps


def _stats(row: dict[str, Any], col: str) -> TeamStats:
    return TeamStats(
        kills=_int(row.get(f"{col}Kills")),
        gold=_int(row.get(f"{col}Gold")),
        dragons=_int(row.get(f"{col}Dragons")),
        barons=_int(row.get(f"{col}Barons")),
        towers=_int(row.get(f"{col}Towers")),
        heralds=_int(row.get(f"{col}RiftHeralds")),
        grubs=_int(row.get(f"{col}VoidGrubs")),
        atakhans=_int(row.get(f"{col}Atakhans")),
        inhibitors=_int(row.get(f"{col}Inhibitors")),
    )


def build_sets(raw: dict[str, Any]) -> list[SetRecord]:
    """원본에서 세트 기록을 만든다. 시작 시각 순으로 돌려준다."""
    sets: list[SetRecord] = []
    for league, _pattern in LEAGUES:
        data = raw["leagues"].get(league) or {}
        shorts = {(t.get("Name") or "").strip(): t["Short"].strip() for t in data.get("teams") or [] if t.get("Short")}
        drafts = {d.get("GameId"): d for d in data.get("drafts") or []}
        set_mvp = {v.get("GameId"): official_player(v.get("MVP")) for v in data.get("vods") or []}
        players: dict[str, list[dict[str, Any]]] = {}
        for p in data.get("players") or []:
            players.setdefault(p.get("GameId") or "", []).append(p)

        for g in data.get("games") or []:
            game_id = g.get("GameId") or ""
            name_blue, name_red = (g.get("Team1") or "").strip(), (g.get("Team2") or "").strip()
            if not game_id or not name_blue or not name_red or "showmatch" in game_id.lower():
                continue
            blue, red = resolve_team(name_blue, shorts), resolve_team(name_red, shorts)
            by_name = {name_blue: blue, name_red: red}
            winner = by_name.get((g.get("WinTeam") or "").strip())

            draft: list[DraftStep] = []
            first_pick: int | None = None
            d = drafts.get(game_id)
            if d:
                first = resolve_team((d.get("Team1") or "").strip(), shorts)
                second = resolve_team((d.get("Team2") or "").strip(), shorts)
                if {first.id, second.id} == {blue.id, red.id}:
                    draft, first_pick = _draft(d, first, second), first.id

            lines = []
            for p in sorted(players.get(game_id, []), key=lambda p: (_int(p.get("Side")), _int(p.get("RoleN")))):
                team = by_name.get((p.get("Team") or "").strip()) or resolve_team((p.get("Team") or "").strip(), shorts)
                lines.append(
                    PlayerLine(
                        team_id=team.id,
                        player=(p.get("Link") or "").split(" (")[0].strip(),
                        champion=(p.get("Champion") or "").strip(),
                        role=role_name(p.get("Role")),
                        kills=_int(p.get("Kills")),
                        deaths=_int(p.get("Deaths")),
                        assists=_int(p.get("Assists")),
                        cs=_int(p.get("CS")),
                        gold=_int(p.get("Gold")),
                        damage=_int(p.get("Dmg")),
                        vision=_int(p.get("Vision")),
                    )
                )

            sets.append(
                SetRecord(
                    game_id=game_id,
                    match_id=stable_id(g.get("MatchId") or ""),
                    league=league,
                    number=_int(g.get("N")) or 1,
                    start=_iso(g.get("Start")),
                    patch=(g.get("Patch") or "").strip(),
                    blue=blue,
                    red=red,
                    winner_id=winner.id if winner else None,
                    length_min=float(g["Len"]) if g.get("Len") else None,
                    first_pick_id=first_pick,
                    official_mvp=set_mvp.get(game_id),
                    draft=draft,
                    blue_stats=_stats(g, "Team1"),
                    red_stats=_stats(g, "Team2"),
                    players=lines,
                    rpg=(g.get("Rpg") or "").strip(),
                    vod=(g.get("VOD") or "").strip(),
                )
            )
    sets.sort(key=lambda s: (s.start, s.match_id, s.number))
    return sets


def load_sets(data_dir: Path) -> list[SetRecord]:
    """data/raw/ 에 있는 모든 연도의 세트 기록."""
    out: list[SetRecord] = []
    for path in sorted((data_dir / "raw").glob("leaguepedia-*.json")):
        out += build_sets(json.loads(path.read_text(encoding="utf-8")))
    out.sort(key=lambda s: (s.start, s.match_id, s.number))
    return out


def load_timelines(data_dir: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path in sorted((data_dir / "raw").glob("timelines-*.json")):
        out.update({k: v for k, v in json.loads(path.read_text(encoding="utf-8")).items() if v})
    return out
