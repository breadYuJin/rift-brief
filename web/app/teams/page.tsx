import type { Metadata } from "next";
import { Standings } from "@/components/Standings";
import { getLeagues } from "@/lib/data";

export const metadata: Metadata = { title: "팀 전적" };

export default function TeamsPage() {
  const leagues = getLeagues();
  return (
    <>
      <h1 className="page-title">팀 전적</h1>
      <p className="page-lede">
        현재 시즌의 스테이지별 전적입니다. 승수와 세트 득실 순으로 정렬해 공식 순위와 다를 수 있습니다. 최근 5경기는
        오른쪽이 가장 최근이고, 채운 칸이 승리입니다.
      </p>
      {leagues.length === 0 && <p className="empty">등록된 리그가 없습니다.</p>}
      {leagues.map((l) => (
        <section key={l.id} className="league-block">
          <h2 className="league-block__title">
            {l.name} {l.serie}
            <span className={`status status--${l.status === "진행 중" ? "on" : "off"}`}>{l.status}</span>
          </h2>
          {l.stages.length === 0 && <p className="empty">아직 치른 경기가 없습니다.</p>}
          {l.stages.map((s) => (
            <div key={s.name} className="stage">
              <h3 className="section-title">{s.name}</h3>
              <Standings stage={s} />
            </div>
          ))}
        </section>
      ))}
    </>
  );
}
