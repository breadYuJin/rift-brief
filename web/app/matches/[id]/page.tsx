import type { Metadata } from "next";
import Link from "next/link";
import { OfficialPicks } from "@/components/match/OfficialPicks";
import { RatingBoard } from "@/components/match/RatingBoard";
import { SeasonTable, type SeasonRow } from "@/components/match/SeasonTable";
import { Badges } from "@/components/MatchCard";
import { Scoreboard } from "@/components/Scoreboard";
import { SetStrip } from "@/components/SetStrip";
import { MockPlayer } from "@/components/sets/MockPlayer";
import { SetExplorer } from "@/components/sets/SetExplorer";
import { championName, getAwards, getMatchSets, getModels, getPlayers, getResults } from "@/lib/data";
import { formatDay, formatTime } from "@/lib/format";
import { officialPicks } from "@/lib/official";
import { stageLabel } from "@/lib/select";
import { toMockView, toSetViews, type SetView } from "@/lib/sets";
import { REPO_URL } from "@/lib/site";
import type { Team } from "@/lib/types";

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

/** 이 경기에 실제로 나온 선수끼리(1세트 출전 기준) 시즌 평균을 맞세운다. 둘 다 시즌 기록이 있는 포지션만. */
function seasonRows(teams: [Team, Team], firstSet: SetView | undefined): SeasonRow[] {
  const players = getPlayers();
  const byName = (team: Team) => new Map((players[String(team.id)] ?? []).map((p) => [p.player, p]));
  const [seasonA, seasonB] = teams.map(byName);
  return (firstSet?.matchups ?? []).flatMap((m) => {
    const a = seasonA.get(m.a.player);
    const b = seasonB.get(m.b.player);
    return a && b ? [{ role: m.role, a, b }] : [];
  });
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
  const teams: [Team, Team] = [match.team_a, match.team_b];
  const data = getMatchSets(match.id);
  const sets = data ? toSetViews(data, match, championName) : [];
  const mock = data?.mock ? toMockView(data.mock, match.team_a, match.team_b, championName) : null;
  const ratings = data?.ratings ?? [];
  const season = seasonRows(teams, sets[0]);
  const picks = officialPicks(match, getAwards()[String(match.id)] ?? null);
  const minVotes = getModels()?.ratings?.feedback.min_votes ?? 3;

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
        <OfficialPicks picks={picks} />
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
            모이면 일부만 반영합니다.{" "}
            {(picks.pick || picks.award) && "이름 옆 표시는 주최 측이 뽑은 선수이고, 이 평점과는 따로 정해집니다."}
          </p>
          <RatingBoard teams={teams} ratings={ratings} winnerId={match.winner_id} picks={picks} />
        </section>
      )}

      {sets.length > 0 && (
        <section className="block" id="sets">
          <h2>세트별 기록</h2>
          <SetExplorer sets={sets} matchId={match.id} repoUrl={REPO_URL} minVotes={minVotes} />
        </section>
      )}

      {season.length > 0 && (
        <section className="block">
          <h2>시즌 평균 맞대결</h2>
          <p className="block__hint">
            이 경기에 나온 선수들의 2026 시즌 전체 평균입니다. 평점은 세트별 평점의 평균입니다. 더 높은 쪽이 밝게
            보입니다.
          </p>
          <SeasonTable teams={teams} rows={season} />
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
