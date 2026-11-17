"use client";

import Link from "next/link";
import { useState } from "react";
import type { Bracket, Match } from "@/lib/types";
import { TeamLogo } from "./Assets";

export interface BracketEntry {
  key: string;
  label: string;
  bracket: Bracket;
  matches: Record<number, Match>;
  briefed: number[];
}

const NOTE_CLASS: Record<string, string> = { 우승: "win", 준우승: "second", 진출: "pass", 탈락: "out" };

function Row({ id, acr, name, score, won, lost, note }: { id: number; acr: string; name: string; score: number | null; won: boolean; lost: boolean; note: string }) {
  return (
    <span className={`bk__row${won ? " is-won" : ""}${lost ? " is-lost" : ""}`}>
      <abbr className="bk__acr" title={name}>
        <TeamLogo id={id} size={18} />
        {acr}
      </abbr>
      {note && <span className={`bk__note bk__note--${NOTE_CLASS[note] ?? "pass"}`}>{note}</span>}
      <span className="bk__score">{score ?? ""}</span>
    </span>
  );
}

function Slot({ match, noteA, noteB, linked }: { match: Match; noteA: string; noteB: string; linked: boolean }) {
  const done = match.winner_id !== null;
  const rows = (
    <>
      <Row
        id={match.team_a.id}
        acr={match.team_a.acronym}
        name={match.team_a.name}
        score={done ? match.score_a : null}
        won={done && match.winner_id === match.team_a.id}
        lost={done && match.winner_id !== match.team_a.id}
        note={noteA}
      />
      <Row
        id={match.team_b.id}
        acr={match.team_b.acronym}
        name={match.team_b.name}
        score={done ? match.score_b : null}
        won={done && match.winner_id === match.team_b.id}
        lost={done && match.winner_id !== match.team_b.id}
        note={noteB}
      />
    </>
  );
  return linked ? (
    <Link className="bk__match" href={`/matches/${match.id}/`}>
      {rows}
    </Link>
  ) : (
    <span className="bk__match">{rows}</span>
  );
}

/** 대회 대진표. 위의 버튼으로 대회를 고르고, 라운드별로 누가 올라가고 떨어졌는지 본다. */
export function BracketBoard({ entries }: { entries: BracketEntry[] }) {
  const [key, setKey] = useState(entries[0]?.key ?? "");
  const current = entries.find((e) => e.key === key) ?? entries[0];
  if (!current) return <p className="empty">아직 대진표가 있는 대회가 없습니다.</p>;
  const { bracket } = current;
  const briefed = new Set(current.briefed);
  const teams = new Set(bracket.rounds[0]?.slots.flatMap((s) => [current.matches[s.match_id]?.team_a.id, current.matches[s.match_id]?.team_b.id]));

  return (
    <div className="bracket">
      <div className="filter" role="group" aria-label="대회 선택">
        {entries.map((e) => (
          <button key={e.key} type="button" className="filter__chip" aria-pressed={e.key === current.key} onClick={() => setKey(e.key)}>
            {e.label}
          </button>
        ))}
      </div>
      <p className="bracket__hint">
        {bracket.tree
          ? `${teams.size}강부터 한 번 지면 탈락하는 토너먼트입니다.`
          : "라운드 순서대로 본 대진입니다. 지고도 다음 라운드에 다시 나오는 팀은 패자조로 내려간 팀입니다."}
      </p>
      <div className="bk-scroll" key={current.key}>
        <ol className={`bk${bracket.tree ? " bk--tree" : ""}`}>
          {bracket.rounds.map((round) => (
            <li key={round.name} className="bk__round">
              <p className="bk__label">{round.name}</p>
              <ul className="bk__slots">
                {round.slots.map((slot) => {
                  const match = current.matches[slot.match_id];
                  if (!match) return null;
                  return (
                    <li key={slot.match_id} className="bk__slot">
                      <Slot match={match} noteA={slot.note_a} noteB={slot.note_b} linked={briefed.has(match.id)} />
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
