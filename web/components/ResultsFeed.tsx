"use client";

import { useEffect, useMemo, useState } from "react";
import type { Brief } from "@/lib/types";
import { ResultCard } from "./MatchCard";

const STORAGE_KEY = "rift-brief:team";

/** 최근 결과 카드 목록과 팀 필터. 고른 팀은 이 브라우저에만 기억한다. */
export function ResultsFeed({ briefs }: { briefs: Brief[] }) {
  const [team, setTeam] = useState<string>("");

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
      <div className="cards">
        {shown.map((b) => (
          <ResultCard key={b.match.id} brief={b} />
        ))}
      </div>
    </>
  );
}
