"""data/archive/*.json (수집해 둔 시즌 기록)을 읽는 데이터 소스."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import LeagueFeed, Match


def archive_files(archive_dir: Path) -> list[Path]:
    return sorted(archive_dir.glob("*.json")) if archive_dir.is_dir() else []


class ArchiveSource:
    def __init__(self, archive_dir: Path):
        self._feeds: list[LeagueFeed] = []
        notes: list[str] = []
        for path in archive_files(archive_dir):
            data = json.loads(path.read_text(encoding="utf-8"))
            self._feeds += [LeagueFeed.model_validate(f) for f in data.get("leagues", [])]
            notes.append(f"{data.get('source', '기록')} {data.get('year', '')}, {data.get('fetched_on', '')} 기준")
        # 화면 안내문에 쓰는 출처 설명.
        self.note = ", ".join(notes)
        self._by_team: dict[int, list[Match]] = {}
        for feed in self._feeds:
            for m in feed.matches:
                for team in (m.team_a, m.team_b):
                    self._by_team.setdefault(team.id, []).append(m)

    def leagues(self) -> list[LeagueFeed]:
        return self._feeds

    def team_matches(self, team_id: int) -> list[Match]:
        return self._by_team.get(team_id, [])
