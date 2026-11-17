import type { Metadata } from "next";
import Link from "next/link";
import { getCollectStatus, getMeta, getModels } from "@/lib/data";
import { formatStamp } from "@/lib/format";

export const metadata: Metadata = { title: "만드는 방식" };

const BRIEF = [
  ["수집", "끝난 경기와 두 팀의 최근 전적, 맞대결 기록, 세트별 킬·오브젝트·교전 기록을 모읍니다."],
  ["분석", "스코어와 세트 순서로 풀세트, 역전, 연승 저지 같은 특징을 찾고 경기의 관점을 정합니다."],
  ["작성", "정리된 데이터만 근거로 헤드라인과 요약 세 줄을 씁니다."],
  ["검증", "요약에 나온 숫자와 승패를 데이터와 대조합니다. 맞지 않으면 작성 단계로 돌려보냅니다."],
  ["편집", "결승·플레이오프 여부, 순위, 경기 특징으로 점수를 매겨 홈의 주요 경기를 고릅니다."],
];

const DRAFT = [
  ["밴픽 예측", "이번 패치의 공식 경기 기록으로 두 팀의 금지·선택 후보에 순위를 매깁니다. 세트가 끝나면 다음 세트 예상을 다시 냅니다."],
  ["팀 에이전트 둘", "각자 한 팀을 맡아, 후보 가운데 하나를 골라 실제 밴픽 순서대로 한 수씩 번갈아 둡니다."],
  ["해설", "끝난 모의 밴픽을 보고 관전 포인트를 정리합니다."],
];

export default function AboutPage() {
  const meta = getMeta();
  const models = getModels();
  const collect = Object.entries(getCollectStatus());
  const usesModel = meta.llm !== "template";
  return (
    <article className="prose">
      <h1 className="page-title">만드는 방식</h1>
      <p className="page-lede">
        역할이 다른 에이전트들이 차례로 일해서 브리핑과 예측을 만듭니다. 사람이 손으로 올리는 것은 없습니다.
      </p>

      <h2>경기 브리핑</h2>
      <ol className="trace trace--steps">
        {BRIEF.map(([agent, note]) => (
          <li key={agent}>
            <span className="trace__agent">{agent}</span>
            <span className="trace__note">{note}</span>
          </li>
        ))}
      </ol>
      <p>
        검증에서 두 번 떨어지면 규칙으로 만든 문장으로 바꿔 올립니다. 각 경기 페이지 아래에서 그 경기의 과정을 볼
        수 있습니다.
      </p>

      <h2>모의 밴픽</h2>
      <ol className="trace trace--steps">
        {DRAFT.map(([agent, note]) => (
          <li key={agent}>
            <span className="trace__agent">{agent}</span>
            <span className="trace__note">{note}</span>
          </li>
        ))}
      </ol>
      <p>
        에이전트는 예측 모델이 뽑은 후보 안에서만 고를 수 있어, 없는 챔피언이나 이미 나온 챔피언을 두지 못합니다.
        결과와 검증 수치는 <Link href="/draft/">밴픽 예측</Link>에 있습니다.
      </p>

      <h2>예정 경기 프리뷰</h2>
      <p>패널 둘이 각 팀의 입장에서 동시에 근거를 내고, 사회자 에이전트가 관전 포인트로 정리합니다.</p>

      <h2>승률과 경기 후 분석</h2>
      <p>
        승률은 밴픽이 끝난 시점에 한 번 계산합니다. 두 팀의 전력 차와 진영, 고른 챔피언을 봅니다. 교전 횟수와
        위치, 오브젝트 순서, 정글 동선은 경기 뒤에 올라오는 분 단위 기록에서 뽑습니다.
        {models && (
          <>
            {" "}
            지금까지 {models.counts.sets}세트의 밴픽과 {models.counts.timelines}세트의 분 단위 기록을 받았습니다.
          </>
        )}
      </p>

      {collect.length > 0 && (
        <>
          <h2>자료 수집</h2>
          <p>하루 네 번 아래 자료를 자동으로 받아 옵니다. 열쇠가 필요한 것은 넣는 즉시 켜집니다.</p>
          <div className="table-wrap">
            <table className="table collect">
              <thead>
                <tr>
                  <th scope="col">받는 것</th>
                  <th scope="col">상태</th>
                  <th scope="col">내용</th>
                  <th scope="col">마지막 수집</th>
                </tr>
              </thead>
              <tbody>
                {collect.map(([name, c]) => (
                  <tr key={name}>
                    <th scope="row">{c.what}</th>
                    <td>
                      <span className={`collect__state collect__state--${c.state === "수집됨" ? "ok" : c.state === "실패" ? "bad" : "wait"}`}>
                        {c.state}
                      </span>
                    </td>
                    <td className="collect__note">{c.note}</td>
                    <td>{c.at ? formatStamp(c.at) : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h2>일정과 팀 전적</h2>
      <p>
        리그 일정과 팀 전적은 시즌의 경기 결과를 그대로 집계한 것입니다. 전적표는 승수와 세트 득실만으로 정렬하므로
        상대 전적까지 따지는 공식 순위와 다를 수 있습니다.
      </p>

      <h2>선수 평점</h2>
      <p>
        세트가 끝나면 선수마다 10점 만점 평점을 매깁니다. KDA, 킬 관여율, 데스, 팀 내 피해 비중, 맞상대와의 골드
        차, 시야 점수를 같은 포지션 선수들과 견줘 계산하고, 이긴 쪽에 조금 더합니다. 평균은 6점 안팎입니다. 팬
        투표로 매기는 후푸 평점과 달리 기록만으로 계산한 값입니다.
      </p>

      <h2>아직 없는 것</h2>
      <p>
        경기 중 실시간 밴픽 추적과 킬 장면 영상 바로가기는 준비 중입니다. 영상 바로가기는 공식 채널 영상의
        방송 시각과 경기 기록의 실제 시각을 맞춰 계산하며, 위치가 맞는지 확인한 뒤에 켭니다.
      </p>

      <h2>돌아가는 환경</h2>
      <p>
        에이전트는 LangGraph로 연결되어 GitHub Actions에서 정해진 시간마다 실행됩니다. 결과는 JSON 파일로 저장소에
        쌓이고, Next.js가 정적 페이지로 만들어 GitHub Pages에 올립니다. 현재 글과 모의 밴픽을 쓰는 방식:{" "}
        {usesModel ? `언어 모델 (${meta.llm})` : "언어 모델 없이 규칙으로 작성"}.
      </p>
    </article>
  );
}
