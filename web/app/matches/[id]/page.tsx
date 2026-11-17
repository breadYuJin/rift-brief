import type { Metadata } from "next";
import Link from "next/link";
import { Badges } from "@/components/MatchCard";
import { Scoreboard } from "@/components/Scoreboard";
import { SetStrip } from "@/components/SetStrip";
import { TeamLogo } from "@/components/Assets";
import { Rating } from "@/components/sets/Matchups";
import { MockPlayer } from "@/components/sets/MockPlayer";
import { SetExplorer } from "@/components/sets/SetExplorer";
import { championName, getMatchSets, getModels, getPlayers, getResults } from "@/lib/data";
import { toMockView, toSetViews } from "@/lib/sets";
import { REPO_URL } from "@/lib/site";
import type { PlayerAverage } from "@/lib/types";
import { formatDay, formatTime } from "@/lib/format";
import { stageLabel } from "@/lib/select";

export const dynamicParams = false;

// 정적 export 는 빈 목록을 허용하지 않아서, 결과가 없을 때는 자리표시 경로 하나를 만든다.
export function generateStaticParams() {
  const ids = getResults().map((b) => ({ id: String(b.match.id) }));
  return ids.length ? ids : [{ id: "none" }];
}

type Props = { params: Promise<{ id: string }> };

const find = (id: string) => getResults().find((b) => String(b.match.id) === id);

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const brief = find((await params).id);
  return brief ? { title: brief.headline, description: brief.summary.join(" ") } : { title: "경기를 찾을 수 없음" };
}

export default async function MatchPage({ params }: Props) {
  const brief = find((await params).id);
  if (!brief) {
    return (
      <p className="empty">
        이 경기의 브리핑을 찾을 수 없습니다. <Link href="/">최근 경기 결과로 돌아가기</Link>
      </p>
    );
  }
  const { match } = brief;
  const data = getMatchSets(match.id);
  const sets = data ? toSetViews(data, match, championName) : [];
  const mock = data?.mock ? toMockView(data.mock, match.team_a, match.team_b, championName) : null;
  const players = getPlayers();
  const season = (teamId: number) => new Map((players[String(teamId)] ?? []).map((p) => [p.player, p]));
  const seasonA = season(match.team_a.id);
  const seasonB = season(match.team_b.id);
  // 이 경기에 실제로 나온 선수끼리 시즌 평균을 맞세운다.
  const seasonRows = (sets[0]?.matchups ?? [])
    .map((m) => ({ role: m.role, a: seasonA.get(m.a.player), b: seasonB.get(m.b.player) }))
    .filter((r): r is { role: string; a: PlayerAverage; b: PlayerAverage } => Boolean(r.a && r.b));
  const feedback = getModels()?.ratings?.feedback;
  // 주최 측이 이 경기에서 뽑은 선수. LCK 는 POM(Player of the Match), 결승은 결승 MVP 라고 부른다.
  const officialLabel = match.round === "결승" ? "결승 MVP" : match.league === "LCK" ? "POM" : "경기 MVP";
  const isOfficial = (player: string) => !!match.mvp && match.mvp.toLowerCase() === player.toLowerCase();
  const ROLE_ORDER = ["탑", "정글", "미드", "원딜", "서포터"];
  const ratings = data?.ratings ?? [];
  // 경기 최고 평점은 이긴 팀에서 뽑는다(세트 절반 이상 뛴 선수, 평점 높은 순으로 정렬돼 있다).
  const top = ratings.find((r) => r.team_id === match.winner_id) ?? null;
  const ratingRows = (teamId: number) =>
    ratings
      .filter((r) => r.team_id === teamId)
      .sort((x, y) => ROLE_ORDER.indexOf(x.role) - ROLE_ORDER.indexOf(y.role));
  return (
    <article className="detail">
      <div className="card card--lead">
        <p className="card__meta">
          <span>
            {stageLabel(match)}, {match.best_of}전제
          </span>
          <span>
            {formatDay(match.begin_at)} {formatTime(match.begin_at)}
          </span>
        </p>
        <Scoreboard match={match} recentA={brief.recent_a} recentB={brief.recent_b} size="lg" />
        <SetStrip match={match} detailed />
        <h1 className="card__headline">{brief.headline}</h1>
        <Badges reasons={brief.reasons} tags={brief.tags} />
        {match.mvp && (
          <p className="official">
            <span className="official__label">주최 측 선정 {officialLabel}</span>
            <strong>{match.mvp}</strong>
          </p>
        )}
        <ul className="summary">
          {brief.summary.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      </div>

      {ratings.length > 0 && (
        <section className="block">
          <h2>선수 평점</h2>
          <p className="block__hint">
            세트 기록으로 계산한 10점 만점 점수이고, 이 경기 세트들의 평균입니다. 평균은 6점 안팎입니다. 팬 의견이
            모이면 일부만 반영합니다. {match.mvp && `"${officialLabel}" 표시는 주최 측이 뽑은 선수로, 이 평점과는 따로 정해집니다.`}
          </p>
          <div className="rates">
            {[match.team_a, match.team_b].map((team, i) => (
              <div key={team.id} className={`rates__team rates__team--${i === 0 ? "a" : "b"}`}>
                <p className="rates__head">
                  <TeamLogo id={team.id} size={24} />
                  {team.acronym}
                </p>
                <ul>
                  {ratingRows(team.id).map((r) => (
                    <li key={r.player} className="rates__row">
                      <span className="rates__role">{r.role}</span>
                      <span className="rates__name">
                        {r.player}
                        {isOfficial(r.player) && <span className="rate__official">{officialLabel}</span>}
                      </span>
                      <span className="rates__bar" aria-hidden="true">
                        <span style={{ width: `${r.rating * 10}%` }} />
                      </span>
                      <span className="rates__score">
                        <Rating value={r.rating} best={top?.player === r.player && top.team_id === r.team_id} />
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {sets.length > 0 && (
        <section className="block" id="sets">
          <h2>세트별 기록</h2>
          <SetExplorer sets={sets} matchId={match.id} repoUrl={REPO_URL} minVotes={feedback?.min_votes ?? 3} />
        </section>
      )}

      {seasonRows.length > 0 && (
        <section className="block">
          <h2>시즌 평균 맞대결</h2>
          <p className="block__hint">이 경기에 나온 선수들의 2026 시즌 전체 평균입니다. 평점은 세트별 평점의 평균입니다. 더 높은 쪽이 밝게 보입니다.</p>
          <div className="table-wrap">
            <table className="table season">
              <thead>
                <tr>
                  <th scope="col">{match.team_a.acronym}</th>
                  <th scope="col" className="num">평점</th>
                  <th scope="col" className="num">KDA</th>
                  <th scope="col" className="num">분당 CS</th>
                  <th scope="col" className="num">분당 피해</th>
                  <th scope="col" className="season__role">포지션</th>
                  <th scope="col" className="num">분당 피해</th>
                  <th scope="col" className="num">분당 CS</th>
                  <th scope="col" className="num">KDA</th>
                  <th scope="col" className="num">평점</th>
                  <th scope="col" className="season__b">{match.team_b.acronym}</th>
                </tr>
              </thead>
              <tbody>
                {seasonRows.map(({ role, a, b }) => {
                  const cell = (mine: number, other: number, text: string) => (
                    <td className={`num${mine > other ? " is-more" : ""}`}>{text}</td>
                  );
                  return (
                    <tr key={role}>
                      <th scope="row" className="season__a">{a.player}</th>
                      {cell(a.rating ?? 0, b.rating ?? 0, a.rating?.toFixed(1) ?? "-")}
                      {cell(a.kda, b.kda, a.kda.toFixed(1))}
                      {cell(a.cs_min, b.cs_min, a.cs_min.toFixed(1))}
                      {cell(a.dpm, b.dpm, String(a.dpm))}
                      <td className="season__role">{role}</td>
                      {cell(b.dpm, a.dpm, String(b.dpm))}
                      {cell(b.cs_min, a.cs_min, b.cs_min.toFixed(1))}
                      {cell(b.kda, a.kda, b.kda.toFixed(1))}
                      {cell(b.rating ?? 0, a.rating ?? 0, b.rating?.toFixed(1) ?? "-")}
                      <th scope="row" className="season__b">{b.player}</th>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {mock && (
        <section className="block">
          <h2>경기 전 AI 모의 밴픽</h2>
          <p className="block__hint">
            이 경기 전까지의 기록만 보고 두 에이전트가 번갈아 둔 가상의 1세트 밴픽입니다. 위의 실제 밴픽과 비교해
            보세요.
          </p>
          <MockPlayer mock={mock} />
        </section>
      )}

      <details className="fold">
        <summary>근거로 쓴 데이터 {brief.facts.length}개</summary>
        <p className="block__hint">요약 문장은 아래 항목에 있는 내용과 숫자만 쓰도록 검증됩니다.</p>
        <ul className="facts">
          {brief.facts.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      </details>

      <details className="fold">
        <summary>이 브리핑이 만들어진 과정</summary>
        <p className="block__hint">
          {brief.generated_by === "llm"
            ? "언어 모델이 작성했고, 검증 단계를 통과했습니다."
            : "언어 모델 없이 규칙 기반 문장으로 작성했습니다."}
        </p>
        <ol className="trace">
          {brief.trace.map((s, i) => (
            <li key={i}>
              <span className="trace__agent">{s.agent}</span>
              <span className="trace__note">{s.note}</span>
            </li>
          ))}
        </ol>
      </details>

      <p>
        <Link href="/">최근 경기 결과로 돌아가기</Link>
      </p>
    </article>
  );
}
