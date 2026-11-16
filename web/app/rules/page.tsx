import type { Metadata } from "next";
import { DRAFT_PHASES, RULES_CHECKED, RULES_SEASON, SECTIONS, SOURCES } from "@/content/rules";

export const metadata: Metadata = { title: "리그 규칙" };

function DraftOrder() {
  let n = 0;
  return (
    <figure className="draft">
      <figcaption>
        밴픽 진행 순서. <span className="draft__key draft__key--first">먼저 하는 팀(선픽)</span>
        <span className="draft__key draft__key--second">나중 팀(후픽)</span>
      </figcaption>
      <div className="draft__phases">
        {DRAFT_PHASES.map((p) => (
          <div key={p.label} className="draft__phase">
            <p className="draft__label">{p.label}</p>
            <ol className="draft__turns" start={n + 1}>
              {p.turns.map((who) => {
                n += 1;
                return (
                  <li key={n} className={`draft__turn draft__turn--${who} draft__turn--${p.kind === "밴" ? "ban" : "pick"}`}>
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

export default function RulesPage() {
  return (
    <div className="rules">
      <h1 className="page-title">리그 규칙</h1>
      <p className="page-lede">
        경기를 볼 때 알아 두면 좋은 규칙을 정리했습니다. <strong>{RULES_SEASON}</strong>이며, {RULES_CHECKED}
      </p>
      <nav className="jump" aria-label="규칙 바로가기">
        {SECTIONS.map((s) => (
          <a key={s.id} href={`#${s.id}`}>
            {s.title}
          </a>
        ))}
      </nav>

      {SECTIONS.map((s) => (
        <section key={s.id} id={s.id} className="rule">
          <h2 className="rule__title">{s.title}</h2>
          <p className="rule__lede">{s.lede}</p>
          {s.id === "draft" && <DraftOrder />}
          <dl className="rule__items">
            {s.items.map((item) => (
              <div key={item.term}>
                <dt>{item.term}</dt>
                <dd>{item.body}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}

      <section className="rule">
        <h2 className="rule__title">출처</h2>
        <p className="rule__lede">공식 발표와 보도를 바탕으로 요약했습니다. 정확한 조항은 원문을 확인하세요.</p>
        <ul className="sources">
          {SOURCES.map((src) => (
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
