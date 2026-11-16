import type { Metadata } from "next";
import { Badges } from "@/components/MatchCard";
import { Scoreboard } from "@/components/Scoreboard";
import { getPreviews } from "@/lib/data";
import { formatDay } from "@/lib/format";
import { stageLabel } from "@/lib/select";

export const metadata: Metadata = { title: "예정 경기" };

export default function UpcomingPage() {
  const previews = getPreviews();
  return (
    <>
      <h1 className="page-title">예정 경기</h1>
      <p className="page-lede">
        두 패널이 각 팀의 입장에서 근거를 내고, 사회자가 관전 포인트로 정리합니다. 예상 밴픽은 밴픽 예측에서 볼 수 있습니다.
      </p>
      {previews.length === 0 && (
        <p className="empty">지금은 대진이 확정된 예정 경기가 없습니다. 일정이 잡히면 여기에 올라옵니다.</p>
      )}
      <div className="previews">
        {previews.map((p) => {
              const { team_a: a, team_b: b } = p.match;
              return (
                <article key={p.match.id} className="card card--lead">
                  <p className="card__meta">
                    <span>
                      {formatDay(p.match.begin_at)}, {stageLabel(p.match)}
                    </span>
                    <span>맞대결 {p.h2h === "기록 없음" ? "기록 없음" : `${a.acronym} 기준 ${p.h2h}`}</span>
                  </p>
                  <Scoreboard match={p.match} recentA={p.recent_a} recentB={p.recent_b} size="lg" />
                  <Badges reasons={p.reasons} />
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
      </div>
    </>
  );
}
