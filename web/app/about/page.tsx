import type { Metadata } from "next";
import { getMeta } from "@/lib/data";

export const metadata: Metadata = { title: "만드는 방식" };

const STEPS = [
  ["수집", "PandaScore API에서 끝난 경기와 예정 경기, 두 팀의 최근 전적과 맞대결 기록을 가져옵니다."],
  ["분석", "스코어와 세트 순서로 풀세트, 역전, 연승 저지 같은 특징을 찾고 경기의 관점을 정합니다."],
  ["작성", "정리된 데이터만 근거로 헤드라인과 요약 세 줄을 씁니다."],
  ["검증", "요약에 나온 숫자와 승패를 데이터와 대조합니다. 맞지 않으면 작성 단계로 돌려보냅니다."],
];

export default function AboutPage() {
  const meta = getMeta();
  return (
    <article className="prose">
      <h1 className="page-title">만드는 방식</h1>
      <p className="page-lede">
        경기가 끝나면 역할이 다른 에이전트 넷이 차례로 일해서 브리핑 하나를 만듭니다.
      </p>

      <ol className="trace trace--steps">
        {STEPS.map(([agent, note]) => (
          <li key={agent}>
            <span className="trace__agent">{agent}</span>
            <span className="trace__note">{note}</span>
          </li>
        ))}
      </ol>

      <h2>검증에서 떨어지면</h2>
      <p>
        검증 에이전트가 문제를 적어 돌려보내면 작성 에이전트가 다시 씁니다. 두 번 고쳐도 통과하지 못하면 규칙으로
        만든 문장으로 바꿔 올립니다. 각 경기 페이지 아래에서 그 경기의 과정을 볼 수 있습니다.
      </p>

      <h2>예정 경기 프리뷰</h2>
      <p>
        패널 둘이 각 팀의 입장에서 동시에 근거를 내고, 사회자 에이전트가 어느 편도 들지 않는 관전 포인트로
        정리합니다. 승부 예측이나 승률은 다루지 않습니다.
      </p>

      <h2>다루지 않는 것</h2>
      <p>
        지금 쓰는 데이터에는 일정, 결과, 세트별 승패와 길이만 있습니다. 챔피언, 킬 수, 선수별 기록은 없어서
        요약에도 쓰지 않습니다.
      </p>

      <h2>돌아가는 환경</h2>
      <p>
        에이전트는 LangGraph로 연결되어 GitHub Actions에서 정해진 시간마다 실행됩니다. 결과는 JSON 파일로
        저장소에 쌓이고, Next.js가 정적 페이지로 만들어 GitHub Pages에 올립니다. 현재 작성 방식:{" "}
        {meta.llm === "template" ? "규칙 기반 문장" : `언어 모델 (${meta.llm})`}.
      </p>
    </article>
  );
}
