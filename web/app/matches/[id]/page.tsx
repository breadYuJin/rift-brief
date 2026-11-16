import type { Metadata } from "next";
import Link from "next/link";
import { Tags } from "@/components/ResultsFeed";
import { ScoreLine } from "@/components/ScoreLine";
import { SetStrip } from "@/components/SetStrip";
import { getResults } from "@/lib/data";
import { formatDay, formatTime } from "@/lib/format";

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
  return (
    <article className="detail">
      <p className="lead__meta">
        {match.league}
        {match.stage ? ` ${match.stage}` : ""}, {match.best_of}전제
        <span className="lead__when">
          {formatDay(match.end_at)} {formatTime(match.end_at)} 종료
        </span>
      </p>
      <ScoreLine match={match} size="lg" />
      <SetStrip match={match} detailed />
      <h1 className="lead__headline">{brief.headline}</h1>
      <ul className="summary">
        {brief.summary.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
      <Tags tags={brief.tags} />

      <section className="block">
        <h2>근거로 쓴 데이터</h2>
        <p className="block__hint">요약 문장은 아래 항목에 있는 내용과 숫자만 쓰도록 검증됩니다.</p>
        <ul className="facts">
          {brief.facts.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      </section>

      <section className="block">
        <h2>이 브리핑이 만들어진 과정</h2>
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
      </section>

      <p>
        <Link href="/">최근 경기 결과로 돌아가기</Link>
      </p>
    </article>
  );
}
