"""사이트가 읽는 JSON 저장소. 내용이 바뀐 파일만 다시 써서 불필요한 커밋을 막는다."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import BriefRecord, PreviewRecord


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_if_changed(path: Path, payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


class Store:
    def __init__(self, data_dir: Path):
        self.dir = data_dir
        self.meta = _read(data_dir / "meta.json", {})

    def load_results(self) -> list[BriefRecord]:
        return [BriefRecord.model_validate(r) for r in _read(self.dir / "results.json", [])]

    def load_previews(self) -> list[PreviewRecord]:
        return [PreviewRecord.model_validate(r) for r in _read(self.dir / "previews.json", [])]

    def save(
        self,
        results: list[BriefRecord],
        previews: list[PreviewRecord],
        *,
        sample: bool,
        llm_name: str,
        archive_size: int,
    ) -> bool:
        results = sorted(results, key=lambda r: r.match.end_at or "", reverse=True)[:archive_size]
        previews = sorted(previews, key=lambda p: p.match.begin_at or "")
        changed = _write_if_changed(self.dir / "results.json", [r.model_dump() for r in results])
        changed |= _write_if_changed(self.dir / "previews.json", [p.model_dump() for p in previews])

        now = datetime.now(timezone.utc)
        year, week, _ = now.isocalendar()
        meta = {
            "updated_at": now.isoformat(timespec="seconds") if changed else self.meta.get("updated_at"),
            # 주 1회는 값이 바뀌어 커밋이 생긴다 → 비시즌에도 예약 워크플로가 비활성화되지 않는다.
            "heartbeat": f"{year}-W{week:02d}",
            "sample": sample,
            "llm": llm_name,
        }
        if meta["updated_at"] is None:
            meta["updated_at"] = now.isoformat(timespec="seconds")
        changed |= _write_if_changed(self.dir / "meta.json", meta)
        return changed
