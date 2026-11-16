import type { Metadata } from "next";
import { FixtureRow } from "@/components/FixtureRow";
import { getLeagues, getResults } from "@/lib/data";
import { groupByDay } from "@/lib/format";

export const metadata: Metadata = { title: "리그 일정" };

export default function SchedulePage() {
  const leagues = getLeagues();
  const briefed = new Set(getResults().map((r) => r.match.id));
  return (
    <>
      <h1 className="page-title">리그 일정</h1>
      <p className="page-lede">현재 시즌의 경기를 날짜순으로 봅니다. 시각은 모두 한국 시간입니다.</p>
      {leagues.length > 1 && (
        <nav className="jump" aria-label="리그 바로가기">
          {leagues.map((l) => (
            <a key={l.id} href={`#league-${l.id}`}>
              {l.name}
            </a>
          ))}
        </nav>
      )}
      {leagues.length === 0 && <p className="empty">등록된 리그 일정이 없습니다.</p>}
      {leagues.map((l) => {
        const pending = l.matches.filter((m) => m.status !== "finished");
        const done = l.matches.filter((m) => m.status === "finished").reverse();
        return (
          <section key={l.id} id={`league-${l.id}`} className="league-block">
            <h2 className="league-block__title">
              {l.name} {l.serie}
              <span className={`status status--${l.status === "진행 중" ? "on" : "off"}`}>{l.status}</span>
            </h2>
            <div className="split">
              <div>
                <h3 className="section-title">예정·진행 중</h3>
                {pending.length === 0 && <p className="empty">대진이 확정된 예정 경기가 없습니다.</p>}
                {groupByDay(pending, (m) => m.begin_at).map(([day, items]) => (
                  <div key={day} className="fx-group">
                    <h4 className="fx-group__day">{day}</h4>
                    <ul className="fx-list">
                      {items.map((m) => (
                        <FixtureRow key={m.id} match={m} />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <div>
                <h3 className="section-title">지난 경기</h3>
                {done.length === 0 && <p className="empty">아직 끝난 경기가 없습니다.</p>}
                {groupByDay(done, (m) => m.begin_at).map(([day, items]) => (
                  <div key={day} className="fx-group">
                    <h4 className="fx-group__day">{day}</h4>
                    <ul className="fx-list">
                      {items.map((m) => (
                        <FixtureRow key={m.id} match={m} href={briefed.has(m.id) ? `/matches/${m.id}/` : undefined} />
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </section>
        );
      })}
    </>
  );
}
