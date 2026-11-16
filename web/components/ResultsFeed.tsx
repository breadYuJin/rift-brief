"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { formatTime, groupByDay } from "@/lib/format";
import type { Brief } from "@/lib/types";
import { ScoreLine } from "./ScoreLine";
import { SetStrip } from "./SetStrip";

const STORAGE_KEY = "rift-brief:team";

function matchMeta(b: Brief) {
  return `${b.match.league}${b.match.stage ? ` ${b.match.stage}` : ""}, ${b.match.best_of}전제`;
}

export function ResultsFeed({ briefs }: { briefs: Brief[] }) {
  const [team, setTeam] = useState<string>("");

  // 고른 팀은 이 브라우저에만 기억한다. 저장소를 못 쓰는 환경이면 그냥 넘어간다.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) setTeam(saved);
    } catch {}
  }, []);

  const choose = (next: string) => {
    setTeam(next);
    try {
      if (next) window.localStorage.setItem(STORAGE_KEY, next);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch {}
  };

  const teams = useMemo(() => {
    const count = new Map<string, number>();
    for (const b of briefs)
      for (const t of [b.match.team_a.acronym, b.match.team_b.acronym]) count.set(t, (count.get(t) ?? 0) + 1);
    return [...count.entries()].sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0])).map(([t]) => t);
  }, [briefs]);

  // 저장해 둔 팀이 지금 데이터에 없으면 전체를 보여 준다.
  const active = teams.includes(team) ? team : "";
  const shown = active
    ? briefs.filter((b) => b.match.team_a.acronym === active || b.match.team_b.acronym === active)
    : briefs;

  if (briefs.length === 0) {
    return <p className="empty">아직 올라온 경기 결과가 없습니다. 다음 경기가 끝나면 브리핑이 올라옵니다.</p>;
  }

  const [lead, ...rest] = shown;
  return (
    <>
      <div className="filter" role="group" aria-label="팀으로 걸러 보기">
        <button type="button" className="filter__chip" aria-pressed={active === ""} onClick={() => choose("")}>
          전체
        </button>
        {teams.map((t) => (
          <button key={t} type="button" className="filter__chip" aria-pressed={active === t} onClick={() => choose(t)}>
            {t}
          </button>
        ))}
      </div>

      {lead && (
        <article className="lead">
          <p className="lead__meta">
            {matchMeta(lead)}
            <span className="lead__when">
              {groupByDay([lead], (b) => b.match.end_at)[0][0]} {formatTime(lead.match.end_at)} 종료
            </span>
          </p>
          <ScoreLine match={lead.match} size="lg" />
          <SetStrip match={lead.match} detailed />
          <h2 className="lead__headline">
            <Link href={`/matches/${lead.match.id}/`}>{lead.headline}</Link>
          </h2>
          <ul className="summary">
            {lead.summary.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
          <Tags tags={lead.tags} />
        </article>
      )}

      {groupByDay(rest, (b) => b.match.end_at).map(([day, items]) => (
        <section key={day} className="day">
          <h2 className="day__title">{day}</h2>
          {items.map((b) => (
            <article key={b.match.id} className="row">
              <div className="row__score">
                <ScoreLine match={b.match} />
                <SetStrip match={b.match} />
                <p className="row__meta">{matchMeta(b)}</p>
              </div>
              <div className="row__body">
                <h3 className="row__headline">
                  <Link href={`/matches/${b.match.id}/`}>{b.headline}</Link>
                </h3>
                <ul className="summary">
                  {b.summary.map((line, i) => (
                    <li key={i}>{line}</li>
                  ))}
                </ul>
                <Tags tags={b.tags} />
              </div>
            </article>
          ))}
        </section>
      ))}
    </>
  );
}

export function Tags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <ul className="tags" aria-label="경기 특징">
      {tags.map((t) => (
        <li key={t}>{t}</li>
      ))}
    </ul>
  );
}
