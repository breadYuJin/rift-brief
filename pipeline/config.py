"""환경변수 기반 설정. 키가 없으면 샘플/템플릿 모드로 내려간다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    pandascore_token: str = field(default_factory=lambda: os.getenv("PANDASCORE_TOKEN", ""))
    # PandaScore 리그 이름. ID를 아는 경우 PANDASCORE_LEAGUE_IDS 로 덮어쓴다.
    league_names: list[str] = field(
        default_factory=lambda: _csv(os.getenv("LEAGUES", "LCK,Worlds,Mid-Season Invitational"))
    )
    league_ids: list[int] = field(
        default_factory=lambda: [int(v) for v in _csv(os.getenv("PANDASCORE_LEAGUE_IDS", ""))]
    )
    # 예: "anthropic:claude-haiku-5-5", "google_genai:<모델명>", "openai:<모델명>"
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))))
    past_limit: int = int(os.getenv("PAST_LIMIT", "12"))
    upcoming_limit: int = int(os.getenv("UPCOMING_LIMIT", "6"))
    archive_size: int = int(os.getenv("ARCHIVE_SIZE", "80"))
    max_rewrites: int = int(os.getenv("MAX_REWRITES", "2"))

    @property
    def archive_dir(self) -> Path:
        return self.data_dir / "archive"

    @property
    def mode(self) -> str:
        """live: PandaScore 실시간 / archive: 수집해 둔 시즌 기록 / sample: 가상 팀."""
        if self.pandascore_token:
            return "live"
        if self.archive_dir.is_dir() and any(self.archive_dir.glob("*.json")):
            return "archive"
        return "sample"

    @property
    def sample_mode(self) -> bool:
        return self.mode == "sample"
