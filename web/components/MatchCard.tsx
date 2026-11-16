import Link from "next/link";
import { formatDay, formatTime } from "@/lib/format";
import { stageLabel } from "@/lib/select";
import type { Brief, Preview } from "@/lib/types";
import { Scoreboard } from "./Scoreboard";
import { SetStrip } from "./SetStrip";

export function Badges({ reasons = [], tags = [] }: { reasons?: string[]; tags?: string[] }) {
  // 주요 경기 이유를 먼저, 겹치지 않는 경기 특징을 뒤에 둔다.
  const rest = tags.filter((t) => !reasons.includes(t));
  if (reasons.length + rest.length === 0) return null;
  return (
    <ul className="badges" aria-label="경기 특징">
      {reasons.map((r) => (
        <li key={r} className="badges__badge badges__badge--key">
          {r}
        </li>
      ))}
      {rest.map((t) => (
        <li key={t} className="badges__badge">
          {t}
        </li>
      ))}
    </ul>
  );
}

/** 끝난 경기 카드. lead 는 요약 세 줄을 펼쳐서 보여 준다. */
export function ResultCard({ brief, lead = false }: { brief: Brief; lead?: boolean }) {
  const { match } = brief;
  return (
    <article className={`card${lead ? " card--lead" : ""}`}>
      <p className="card__meta">
        <span>{stageLabel(match)}</span>
        <span>
          {formatDay(match.end_at)} {formatTime(match.end_at)}
        </span>
      </p>
      <Scoreboard match={match} recentA={brief.recent_a} recentB={brief.recent_b} size={lead ? "lg" : "md"} />
      <SetStrip match={match} detailed={lead} />
      <h3 className="card__headline">
        <Link href={`/matches/${match.id}/`}>{brief.headline}</Link>
      </h3>
      <Badges reasons={brief.reasons} tags={brief.tags} />
      {lead ? (
        <ul className="summary">
          {brief.summary.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      ) : (
        <details className="card__more">
          <summary>세 줄 요약 보기</summary>
          <ul className="summary">
            {brief.summary.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </article>
  );
}

/** 예정 경기 카드(주요 경기용). */
export function FixtureCard({ preview }: { preview: Preview }) {
  const { match } = preview;
  return (
    <article className="card">
      <p className="card__meta">
        <span>{stageLabel(match)}</span>
        <span>{formatDay(match.begin_at)}</span>
      </p>
      <Scoreboard match={match} recentA={preview.recent_a} recentB={preview.recent_b} />
      <h3 className="card__headline">
        <Link href="/upcoming/">{preview.watch_points[0]}</Link>
      </h3>
      <Badges reasons={preview.reasons} />
    </article>
  );
}
