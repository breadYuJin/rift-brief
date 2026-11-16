import type { Metadata } from "next";
import { ScoreLine } from "@/components/ScoreLine";
import { getPreviews } from "@/lib/data";
import { formatTime, groupByDay } from "@/lib/format";

export const metadata: Metadata = { title: "예정 경기" };

export default function UpcomingPage() {
  const previews = getPreviews();
  return (
    <>
      <h1 className="page-title">예정 경기</h1>
      <p className="page-lede">
        두 패널이 각 팀의 입장에서 근거를 내고, 사회자가 관전 포인트로 정리합니다. 승부 예측은 하지 않습니다.
      </p>
      {previews.length === 0 && (
        <p className="empty">지금은 대진이 확정된 예정 경기가 없습니다. 일정이 잡히면 여기에 올라옵니다.</p>
      )}
      {groupByDay(previews, (p) => p.match.begin_at).map(([day, items]) => (
        <section key={day} className="day">
          <h2 className="day__title">{day}</h2>
          {items.map((p) => {
            const { team_a: a, team_b: b } = p.match;
            return (
              <article key={p.match.id} className="preview">
                <p className="lead__meta">
                  {p.match.league}
                  {p.match.stage ? ` ${p.match.stage}` : ""}, {p.match.best_of}전제
                  <span className="lead__when">{formatTime(p.match.begin_at)} 시작</span>
                </p>
                <ScoreLine match={p.match} size="lg" />
                <dl className="stats">
                  <div>
                    <dt>{a.acronym} 최근 성적</dt>
                    <dd>{p.form_a}</dd>
                  </div>
                  <div>
                    <dt>{b.acronym} 최근 성적</dt>
                    <dd>{p.form_b}</dd>
                  </div>
                  <div>
                    <dt>맞대결 ({a.acronym} 기준)</dt>
                    <dd>{p.h2h}</dd>
                  </div>
                </dl>
                <div className="debate">
                  <section className="debate__side debate__side--a">
                    <h3>{a.name} 쪽 근거</h3>
                    <ul>
                      {p.case_a.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </section>
                  <section className="debate__side debate__side--b">
                    <h3>{b.name} 쪽 근거</h3>
                    <ul>
                      {p.case_b.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </section>
                </div>
                <section className="watch">
                  <h3>관전 포인트</h3>
                  <ul>
                    {p.watch_points.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </section>
              </article>
            );
          })}
        </section>
      ))}
    </>
  );
}
