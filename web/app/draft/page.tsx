import type { Metadata } from "next";
import Link from "next/link";
import { RankBars, Slots, WinBars } from "@/components/draft/ScoreVisuals";
import { SeriesList } from "@/components/draft/SeriesList";
import { TeamGuess } from "@/components/draft/TeamGuess";
import { PatchMeta, type PatchView } from "@/components/PatchMeta";
import { MockPlayer } from "@/components/sets/MockPlayer";
import { championName, getDraftIndex, getMatchSets, getModels, getPatches } from "@/lib/data";
import { formatDay, formatShortDay } from "@/lib/format";
import { toMockView } from "@/lib/sets";

export const metadata: Metadata = {
  title: "밴픽 예측",
  description: "지난 기록으로 다음 세트의 밴픽을 미리 예상하고, 실제 결과와 맞춰 봅니다.",
};

export default function DraftPage() {
  const models = getModels();
  const index = getDraftIndex();
  if (!models) {
    return (
      <>
        <h1 className="page-title">밴픽 예측</h1>
        <p className="empty">아직 밴픽 기록을 받지 못했습니다. 기록이 쌓이면 예상과 검증 결과가 여기에 올라옵니다.</p>
      </>
    );
  }
  const { holdout, baseline_meta_only: base, rank_hit, holdout_set1: first, holdout_later_sets: later } = models.draft;
  const win = models.win.report;
  const latest = index.recent.find((s) => s.has_mock);
  const latestSets = latest ? getMatchSets(latest.match_id) : null;
  const latestMock =
    latest && latestSets?.mock ? toMockView(latestSets.mock, latest.team_a, latest.team_b, championName) : null;
  // 한 팀이 한 세트에 고르는(금지하는) 챔피언은 5개다. 적중률 × 5 = 평균 적중 수.
  const perTeam = (recall: number) => (recall * 5).toFixed(1);
  const pickHits = holdout.pick_hits_10;
  const banHits = holdout.ban_hits_10;
  const patches: PatchView[] = getPatches().map((p) => ({
    patch: p.patch,
    sets: p.sets,
    period: `${formatShortDay(p.from)}부터 ${formatShortDay(p.to)}까지`,
    leagues: p.leagues.join(", "),
    champions: p.champions.slice(0, 12).map((c) => ({
      name: championName(c.champion),
      role: c.role,
      picks: c.picks,
      bans: c.bans,
      presence: c.presence,
      winRate: c.win_rate,
      change: c.change,
    })),
  }));
  const winBars = [
    { label: "항상 블루 진영을 고르면", value: win.blue_rate.accuracy, key: "base" },
    { label: "밴픽 전 (전력과 진영)", value: win.before_draft.accuracy, key: "before" },
    { label: "밴픽 후 (조합까지)", value: win.after_draft.accuracy, key: "after" },
  ];
  return (
    <>
      <h1 className="page-title">밴픽 예측</h1>
      <p className="page-lede">
        경기 전에 두 팀의 밴픽을 미리 예상해 두고, 한 세트가 끝날 때마다 그 세트를 반영해 다음 세트 예상을 다시 냅니다.
        예상은 모두 그 시점 이전 기록만으로 만듭니다.
      </p>

      {patches.length > 0 && (
        <section className="score">
          <h2 className="section-title">패치별 메타</h2>
          <p className="score__basis score__basis--top">
            패치가 바뀌면 자주 나오는 챔피언도 바뀝니다. 그래서 예상은 그 패치가 적용된 뒤의 공식 경기만 보고 냅니다.
            지난 시즌 기록은 쓰지 않습니다.
          </p>
          <PatchMeta patches={patches} />
        </section>
      )}

      <section className="score">
        <h2 className="section-title">얼마나 맞았나</h2>
        <div className="score__grid">
          <div className="score__item">
            <p className="score__q">한 팀이 고른 챔피언 5개 중, 예상 10개 안에 있던 것</p>
            <p className="score__a">
              <Slots value={pickHits} kind="pick" />
              <strong>평균 {pickHits.toFixed(1)}개</strong>
            </p>
            <p className="score__note">
              팀 구분 없이 그 패치의 흐름만 봐도 {perTeam(base.pick_recall_10)}개입니다. 올해는 한 시리즈에서 쓴
              챔피언을 다시 못 쓰는 규칙이라 픽은 맞히기 어렵습니다.
            </p>
          </div>
          <div className="score__item">
            <p className="score__q">한 팀이 금지한 챔피언 5개 중, 예상 10개 안에 있던 것</p>
            <p className="score__a">
              <Slots value={banHits} kind="ban" />
              <strong>평균 {banHits.toFixed(1)}개</strong>
            </p>
            <p className="score__note">
              패치 흐름만 볼 때는 {perTeam(base.ban_recall_10)}개입니다. 시리즈 1세트는 {perTeam(first.ban_recall_10)}
              개, 앞 세트를 반영한 2세트부터는 {perTeam(later.ban_recall_10)}
              개로 올라갑니다.
            </p>
          </div>
        </div>
        <p className="score__basis">
          2026 시즌 {models.counts.drafted}세트 가운데 시간순으로 뒤쪽 {holdout.sets}세트에서 잰 값입니다. 계산 방식은
          앞쪽 세트로만 정했습니다.
        </p>

        <div className="score__grid">
          <figure className="score__item">
            <figcaption className="score__q">예상 순위별로 실제 맞은 비율 (픽, %)</figcaption>
            <RankBars rates={rank_hit.pick} kind="pick" />
          </figure>
          <figure className="score__item">
            <figcaption className="score__q">예상 순위별로 실제 맞은 비율 (밴, %)</figcaption>
            <RankBars rates={rank_hit.ban} kind="ban" />
          </figure>
        </div>
        <p className="score__basis">화면에 챔피언 옆 확률로 나오는 숫자가 이 비율입니다.</p>
      </section>

      <section className="score">
        <h2 className="section-title">밴픽 직후 승률은 얼마나 맞았나</h2>
        <WinBars rows={winBars} />
        <p className="score__basis">
          세트 승자를 맞힌 비율이고, {win.after_draft.sets}세트를 그 시점 이전 기록만으로 예측한 결과입니다. 올해
          기록으로는 조합을 넣어도 거의 달라지지 않았습니다. 그래서 밴픽 후 승률은 밴픽 전 값에서 조금만 움직입니다.
        </p>
      </section>

      <section className="score">
        <h2 className="section-title">다가오는 경기</h2>
        {index.upcoming.length === 0 ? (
          <p className="empty">
            지금은 대진이 잡힌 경기가 없습니다. 일정이 나오면 경기 전 예상 밴픽이 여기에 올라옵니다.
          </p>
        ) : (
          index.upcoming.map((u) => (
            <article key={u.match_id} className="card upcoming-draft">
              <p className="card__meta">
                <span>
                  {u.team_a.acronym} 대 {u.team_b.acronym}
                </span>
                <span>{formatDay(u.begin_at)}</span>
              </p>
              <div className="fc">
                <TeamGuess team={u.team_a} forecast={u.forecast[String(u.team_a.id)]} />
                <TeamGuess team={u.team_b} forecast={u.forecast[String(u.team_b.id)]} />
              </div>
              <MockPlayer mock={toMockView(u.mock, u.team_a, u.team_b, championName)} />
            </article>
          ))
        )}
      </section>

      {latest && latestMock && (
        <section className="score">
          <h2 className="section-title">AI 모의 밴픽</h2>
          <p className="score__basis score__basis--top">
            {formatDay(latest.date)} {latest.team_a.acronym} 대 {latest.team_b.acronym} 경기 전 기록만으로, 두
            에이전트가 실제 순서대로 번갈아 둔 가상의 1세트입니다.{" "}
            <Link href={`/matches/${latest.match_id}/#sets`}>실제 밴픽과 비교하기</Link>
          </p>
          <MockPlayer mock={latestMock} />
        </section>
      )}

      <section className="score">
        <h2 className="section-title">지난 시리즈</h2>
        <SeriesList series={index.recent} />
        <p className="score__basis">숫자는 그 시리즈에서 실제 픽·밴이 예상 10개 안에 들어 있던 비율입니다.</p>
      </section>

      <section className="score prose">
        <h2 className="section-title">어떻게 예상하나</h2>
        <p>
          고를 챔피언은 그 팀이 자주 고른 것과 이번 패치 공식 경기에 자주 나온 것을 합쳐 순위를 매깁니다. 금지할
          챔피언은 상대가 자주 고르는 것, 그 팀이 원래 자주 금지하는 것, 같은 시리즈 앞 세트에서 이미 금지한 것을
          봅니다. 같은 시리즈에서 이미 나온 챔피언은 뺍니다. 새 패치 초반에는 경기 수가 적어 직전 패치의 흐름을 조금
          섞고, 세트가 쌓일수록 그 비중을 줄입니다. 팀 기록도 지난 패치의 것일수록 가볍게 봅니다.
        </p>
        <p>
          경기 중에 밴픽이 한 수씩 진행될 때마다 남은 칸을 다시 예상하는 실시간 추적은 준비 중입니다. 계산 부분은 만들어
          두었고, 실시간 데이터가 연결되면 켜집니다.
        </p>
      </section>
    </>
  );
}
