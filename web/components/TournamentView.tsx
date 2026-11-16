import Link from "next/link";
import { CHECKED, SWISS_KIND_TEXT, SWISS_ROUNDS, TOURNAMENTS, type Tournament } from "@/content/tournaments";

const hrefOf = (slug: string) => (slug === "lck" ? "/rules/" : `/rules/${slug}/`);

function SwissLadder() {
  return (
    <figure className="swiss">
      <figcaption>
        라운드마다 승패가 같은 팀끼리 맞붙습니다. 칸은 그 라운드를 시작할 때의 전적입니다.
      </figcaption>
      <ol className="swiss__rounds">
        {SWISS_ROUNDS.map((r) => (
          <li key={r.round} className="swiss__round">
            <p className="swiss__label">{r.round}라운드</p>
            <ul>
              {r.groups.map((g) => (
                <li key={g.record} className={`swiss__group swiss__group--${g.kind}`}>
                  <span className="swiss__record">{g.record}</span>
                  <span className="swiss__teams">{g.teams}개 팀</span>
                  <span className="swiss__kind">{SWISS_KIND_TEXT[g.kind]}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      <dl className="swiss__result">
        <div>
          <dt>통과 8개 팀</dt>
          <dd>3승 0패 2팀, 3승 1패 3팀, 3승 2패 3팀</dd>
        </div>
        <div>
          <dt>탈락 8개 팀</dt>
          <dd>0승 3패 2팀, 1승 3패 3팀, 2승 3패 3팀</dd>
        </div>
      </dl>
    </figure>
  );
}

/** 대회 하나의 진행 방식. 위쪽 탭으로 다른 대회로 옮겨 간다. */
export function TournamentView({ tournament: t }: { tournament: Tournament }) {
  return (
    <div className="rules">
      <h1 className="page-title">대회 진행 규칙</h1>
      <p className="page-lede">대회마다 진행 순서와 올라가는 조건을 정리했습니다. 대회를 골라 보세요.</p>

      <nav className="tabs" aria-label="대회 선택">
        {TOURNAMENTS.map((x) => (
          <Link key={x.slug} href={hrefOf(x.slug)} className="tabs__tab" aria-current={x.slug === t.slug ? "page" : undefined}>
            {x.tab}
          </Link>
        ))}
      </nav>

      <header className="tour-head">
        <h2 className="tour-head__title">{t.title}</h2>
        <p className="tour-head__season">
          {t.season}, {CHECKED}
        </p>
        <p className="tour-head__lede">{t.lede}</p>
        <dl className="facts-row">
          {t.facts.map((f) => (
            <div key={f.label}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
      </header>

      {t.slug === "swiss" && <SwissLadder />}

      {t.stages.length > 0 && (
        <section className="rule">
          <h3 className="rule__title">{t.stagesTitle}</h3>
          <ol className="flow">
            {t.stages.map((s) => (
              <li key={s.name} className="flow__step">
                <h4 className="flow__name">{s.name}</h4>
                <dl className="flow__body">
                  <div>
                    <dt>참가</dt>
                    <dd>{s.teams}</dd>
                  </div>
                  <div>
                    <dt>방식</dt>
                    <dd>{s.format}</dd>
                  </div>
                  <div>
                    <dt>결과</dt>
                    <dd>{s.outcome}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section className="rule">
        <h3 className="rule__title">{t.notesTitle}</h3>
        <dl className="rule__items">
          {t.notes.map((n) => (
            <div key={n.term}>
              <dt>{n.term}</dt>
              <dd>{n.body}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rule">
        <h3 className="rule__title">출처</h3>
        <p className="rule__lede">
          공식 발표와 보도를 바탕으로 요약했습니다. 용어가 낯설면 <Link href="/terms/">밴픽·용어</Link>를 함께 보세요.
        </p>
        <ul className="sources">
          {t.sources.map((src) => (
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
