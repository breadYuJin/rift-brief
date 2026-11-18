import Link from "next/link";
import { TeamLogo } from "@/components/Assets";
import { formatShortDay, pct } from "@/lib/format";
import type { DraftSeries } from "@/lib/types";

function Hit({ kind, value }: { kind: "pick" | "ban"; value: number }) {
  return (
    <span className={`series__hit series__hit--${kind}`}>
      <span className="series__k">{kind === "pick" ? "픽" : "밴"}</span>
      <span className="series__track" aria-hidden="true">
        <span style={{ width: `${value * 100}%` }} />
      </span>
      {pct(value)}
    </span>
  );
}

/** 지난 시리즈마다 실제 픽·밴이 예상 10개 안에 들어 있던 비율. 줄을 누르면 그 경기의 세트별 기록으로 간다. */
export function SeriesList({ series }: { series: DraftSeries[] }) {
  return (
    <ul className="series">
      {series.map((s) => (
        <li key={s.match_id}>
          <Link href={`/matches/${s.match_id}/#sets`} className="series__row">
            <span className="series__date">{formatShortDay(s.date)}</span>
            <span className="series__teams">
              <TeamLogo id={s.team_a.id} size={18} />
              <span className={s.score_a > s.score_b ? "is-more" : ""}>{s.team_a.acronym}</span>
              <span className="series__score">
                {s.score_a}:{s.score_b}
              </span>
              <span className={s.score_b > s.score_a ? "is-more" : ""}>{s.team_b.acronym}</span>
              <TeamLogo id={s.team_b.id} size={18} />
            </span>
            <Hit kind="pick" value={s.pick_recall} />
            <Hit kind="ban" value={s.ban_recall} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
