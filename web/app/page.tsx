import Link from "next/link";
import { BracketBoard } from "@/components/BracketBoard";
import { FixtureRow } from "@/components/FixtureRow";
import { FixtureCard, ResultCard } from "@/components/MatchCard";
import { ResultsFeed } from "@/components/ResultsFeed";
import { Scoreboard } from "@/components/Scoreboard";
import { Standings } from "@/components/Standings";
import { getLeagues, getPreviews, getResults } from "@/lib/data";
import { formatDay, groupByDay } from "@/lib/format";
import { bracketEntries, liveMatches, nextMatches, pickFeatured, stageLabel } from "@/lib/select";
import { SITE_TAGLINE } from "@/lib/site";
import type { League } from "@/lib/types";

function LeagueSummary({ league: l }: { league: League }) {
  return (
    <div className="league">
      <p className="league__head">
        <span className="league__name">
          {l.name} {l.serie}
        </span>
        <span className={`status status--${l.status === "진행 중" ? "on" : "off"}`}>{l.status}</span>
      </p>
      {l.stages[0] ? (
        <>
          <p className="league__stage">{l.stages[0].name}</p>
          <Standings stage={l.stages[0]} limit={4} />
        </>
      ) : (
        <p className="panel__empty">아직 치른 경기가 없습니다.</p>
      )}
    </div>
  );
}

export default function HomePage() {
  const results = getResults();
  const previews = getPreviews();
  const leagues = getLeagues();
  const featured = pickFeatured(results, previews);
  const live = liveMatches(leagues);
  const next = nextMatches(leagues);
  const [lead, ...moreFeatured] = featured.results;
  const brackets = bracketEntries(leagues, new Set(results.map((r) => r.match.id)));
  const RECENT = 12;
  const lastPlayed = (l: (typeof leagues)[number]) =>
    l.matches.reduce((latest, m) => ((m.begin_at ?? "") > latest ? (m.begin_at ?? "") : latest), "");
  const ongoing = leagues.filter((l) => l.status !== "종료");
  const ended = leagues
    .filter((l) => l.status === "종료")
    .sort((a, b) => lastPlayed(b).localeCompare(lastPlayed(a)))
    .slice(0, 3);

  return (
    <>
      <h1 className="sr-only">{SITE_TAGLINE}</h1>

      {results.length > 0 && (
        <nav className="ticker" aria-label="최근 결과 한 줄 보기">
          <ul>
            {results.slice(0, 8).map((r) => (
              <li key={r.match.id}>
                <Link href={`/matches/${r.match.id}/`}>
                  <Scoreboard match={r.match} size="sm" />
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <div className="home">
        <div className="home__main">
          <section aria-labelledby="featured-title" className="o-1">
            <h2 id="featured-title" className="section-title">
              주요 경기
            </h2>
            {lead ? (
              <>
                <ResultCard brief={lead} lead />
                {(moreFeatured.length > 0 || featured.previews.length > 0) && (
                  <div className="cards">
                    {moreFeatured.map((b) => (
                      <ResultCard key={b.match.id} brief={b} />
                    ))}
                    {featured.previews.map((p) => (
                      <FixtureCard key={p.match.id} preview={p} />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <p className="empty">아직 올라온 경기가 없습니다. 다음 경기가 끝나면 여기에 올라옵니다.</p>
            )}
          </section>

          {brackets.length > 0 && (
            <section aria-labelledby="bracket-title" className="o-1b">
              <h2 id="bracket-title" className="section-title">
                대진표
              </h2>
              <BracketBoard entries={brackets} />
            </section>
          )}

          <section aria-labelledby="results-title" className="o-5">
            <h2 id="results-title" className="section-title">
              최근 결과
            </h2>
            <ResultsFeed briefs={results.slice(0, RECENT)} />
            {results.length > RECENT && (
              <p className="more">
                <Link href="/schedule/">지난 경기 {results.length}건 전체 보기</Link>
              </p>
            )}
          </section>
        </div>

        <aside className="home__side">
          <section aria-labelledby="live-title" className="panel o-2">
            <h2 id="live-title" className="panel__title">
              진행 중인 경기
            </h2>
            {live.length === 0 ? (
              <p className="panel__empty">지금 진행 중인 경기가 없습니다.</p>
            ) : (
              live.map((m) => (
                <div key={m.id} className="panel__live">
                  <p className="card__meta">
                    <span>{stageLabel(m)}</span>
                    <span>{m.best_of}전제</span>
                  </p>
                  <Scoreboard match={m} />
                </div>
              ))
            )}
          </section>

          <section aria-labelledby="leagues-title" className="panel o-4">
            <h2 id="leagues-title" className="panel__title">
              진행 중인 리그
            </h2>
            {ongoing.length === 0 && <p className="panel__empty">지금 진행 중인 리그가 없습니다.</p>}
            {ongoing.map((l) => (
              <LeagueSummary key={l.id} league={l} />
            ))}
            {ended.length > 0 && (
              <>
                <h3 className="panel__sub">최근 끝난 리그</h3>
                {ended.map((l) => (
                  <LeagueSummary key={l.id} league={l} />
                ))}
              </>
            )}
            <p className="panel__more">
              <Link href="/teams/">팀 전적 전체 보기</Link>
            </p>
          </section>

          <section aria-labelledby="next-title" className="panel o-3">
            <h2 id="next-title" className="panel__title">
              다음 경기
            </h2>
            {next.length === 0 ? (
              <p className="panel__empty">대진이 확정된 예정 경기가 없습니다.</p>
            ) : (
              groupByDay(next, (m) => m.begin_at).map(([day, items]) => (
                <div key={day} className="fx-group">
                  <h3 className="fx-group__day">{day}</h3>
                  <ul className="fx-list">
                    {items.map((m) => (
                      <FixtureRow key={m.id} match={m} showStage={false} />
                    ))}
                  </ul>
                </div>
              ))
            )}
            <p className="panel__more">
              <Link href="/schedule/">리그 일정 전체 보기</Link>
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}
