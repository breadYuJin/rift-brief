import type { Metadata } from "next";
import Link from "next/link";
import { DRAFT_PHASES, DRAFT_RULES, GLOSSARY, TERM_SOURCES } from "@/content/terms";

export const metadata: Metadata = { title: "밴픽·용어" };

function DraftOrder() {
  // 단계마다 첫 순번: 앞 단계들의 칸 수를 더한 값 + 1
  const starts = DRAFT_PHASES.map((_, i) => 1 + DRAFT_PHASES.slice(0, i).reduce((sum, p) => sum + p.turns.length, 0));
  return (
    <figure className="draft">
      <figcaption>
        밴픽 진행 순서. <span className="draft__key draft__key--first">먼저 하는 팀(선픽)</span>
        <span className="draft__key draft__key--second">나중 팀(후픽)</span>
      </figcaption>
      <div className="draft__phases">
        {DRAFT_PHASES.map((p, phase) => (
          <div key={p.label} className="draft__phase">
            <p className="draft__label">{p.label}</p>
            <ol className="draft__turns" start={starts[phase]}>
              {p.turns.map((who, i) => {
                const n = starts[phase] + i;
                return (
                  <li
                    key={n}
                    className={`draft__turn draft__turn--${who} draft__turn--${p.kind === "밴" ? "ban" : "pick"}`}
                  >
                    <span className="sr-only">
                      {n}번째: {who === "first" ? "선픽 팀" : "후픽 팀"}
                    </span>
                    {p.kind}
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </div>
    </figure>
  );
}

export default function TermsPage() {
  return (
    <div className="rules">
      <h1 className="page-title">밴픽·용어</h1>
      <p className="page-lede">
        밴픽이 어떻게 진행되는지와, 중계와 이 사이트에 자주 나오는 말을 정리했습니다. 대회별 진행 순서는{" "}
        <Link href="/rules/">대회 규칙</Link>에 있습니다.
      </p>
      <nav className="jump" aria-label="바로가기">
        <a href="#draft">밴픽 규칙</a>
        {GLOSSARY.map((g) => (
          <a key={g.group} href={`#term-${g.group}`}>
            용어: {g.group}
          </a>
        ))}
      </nav>

      <section id="draft" className="rule">
        <h2 className="rule__title">밴픽 규칙</h2>
        <p className="rule__lede">세트마다 두 팀이 번갈아 챔피언을 금지하고 고릅니다. 2026 시즌 기준입니다.</p>
        <DraftOrder />
        <dl className="rule__items">
          {DRAFT_RULES.map((item) => (
            <div key={item.term}>
              <dt>{item.term}</dt>
              <dd>{item.body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rule">
        <h2 className="rule__title">용어 설명</h2>
        {GLOSSARY.map((g) => (
          <div key={g.group} id={`term-${g.group}`} className="glossary">
            <h3 className="section-title">{g.group}</h3>
            <dl className="glossary__terms">
              {g.terms.map((t) => (
                <div key={t.term}>
                  <dt>{t.term}</dt>
                  <dd>{t.body}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </section>

      <section className="rule">
        <h2 className="rule__title">출처</h2>
        <ul className="sources">
          {TERM_SOURCES.map((src) => (
            <li key={src.url}>
              <a href={src.url} rel="noreferrer">
                {src.title}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
