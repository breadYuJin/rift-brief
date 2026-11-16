"""규칙 기반 팩트 도출과 검증 도구.

LLM 에게는 여기서 만든 팩트 목록만 근거로 쓰게 하고, 검증 단계에서
초안의 숫자·승패가 이 팩트와 맞는지 코드로 다시 확인한다.
문장은 팀명 뒤 조사가 틀어지지 않도록 '키: 값' 형태로 쓴다.
"""
from __future__ import annotations

import re

from .schemas import Context, Draft, Match, TeamForm

BANNED_WORDS = ("배당", "베팅", "배팅", "토토", "픽스터", "적중")
HEADLINE_MAX = 34
LINE_MAX = 80


def form_text(form: TeamForm) -> str:
    if not form.recent:
        return "기록 없음"
    return f"{form.wins}승 {form.losses}패"


def _streak_text(streak: int) -> str | None:
    if streak >= 2:
        return f"{streak}연승"
    if streak <= -2:
        return f"{-streak}연패"
    return None


def _context_facts(match: Match, ctx: Context, when: str) -> list[str]:
    facts: list[str] = []
    for team, form in ((match.team_a, ctx.form_a), (match.team_b, ctx.form_b)):
        if not form.recent:
            continue
        facts.append(f"{team.name} {when} 최근 {len(form.recent)}경기: {form_text(form)}")
        streak = _streak_text(form.streak)
        if streak:
            facts.append(f"{team.name} {when} 흐름: {streak} 중")
    if ctx.h2h_a_wins or ctx.h2h_b_wins:
        facts.append(
            f"{when} 최근 맞대결: {match.team_a.name} {ctx.h2h_a_wins}승, {match.team_b.name} {ctx.h2h_b_wins}승"
        )
    return facts


def result_facts(match: Match, ctx: Context) -> tuple[list[str], list[str]]:
    """종료된 경기의 (팩트 목록, 태그)."""
    winner, loser = match.winner, match.loser
    assert winner and loser, "종료된 경기만 처리한다"
    w_score, l_score = max(match.score_a, match.score_b), min(match.score_a, match.score_b)
    need = match.best_of // 2 + 1
    facts = [
        f"대회: {match.league}" + (f" ({match.stage})" if match.stage else ""),
        f"승리 팀: {winner.name} ({winner.acronym})",
        f"패배 팀: {loser.name} ({loser.acronym})",
        f"세트 스코어: {w_score}-{l_score} ({match.best_of}전 {need}선승제)",
    ]
    tags: list[str] = []

    if match.best_of >= 3 and l_score == 0:
        tags.append("셧아웃")
        facts.append(f"{winner.name} 쪽이 한 세트도 내주지 않았다")
    if match.best_of >= 3 and w_score + l_score == match.best_of:
        tags.append("풀세트")
        facts.append("마지막 세트까지 가는 풀세트 승부였다")

    order = [g.winner_id for g in match.games]
    if len(order) == w_score + l_score and order and all(order):
        seq = ", ".join(
            f"{g.position}세트 {winner.acronym if g.winner_id == winner.id else loser.acronym}" for g in match.games
        )
        facts.append(f"세트별 승자: {seq}")
        lost_first = 0
        for wid in order:
            if wid == winner.id:
                break
            lost_first += 1
        if match.best_of >= 5 and lost_first == need - 1:
            tags.append("역스윕")
            facts.append(f"{winner.name} 쪽이 먼저 {lost_first}세트를 내준 뒤 내리 {need}세트를 따냈다")
        elif lost_first >= 1:
            tags.append("역전승")
            facts.append(f"{winner.name} 쪽이 1세트를 내주고 시작해 뒤집었다")
        timed = [g for g in match.games if g.length_min]
        if len(timed) >= 2:
            longest = max(timed, key=lambda g: g.length_min or 0)
            facts.append(f"가장 긴 세트: {longest.position}세트 {longest.length_min}분")

    facts += _context_facts(match, ctx, "경기 전")

    w_form, l_form = (
        (ctx.form_a, ctx.form_b) if winner.id == match.team_a.id else (ctx.form_b, ctx.form_a)
    )
    if l_form.streak >= 3:
        tags.append("연승 저지")
    if w_form.streak <= -2:
        tags.append("연패 탈출")
    if len(w_form.recent) >= 4 and len(l_form.recent) >= 4 and l_form.wins - w_form.wins >= 3:
        tags.append("이변")
        facts.append("경기 전 최근 성적은 패배 팀 쪽이 더 좋았다")
    return facts, tags


def preview_facts(match: Match, ctx: Context) -> list[str]:
    need = match.best_of // 2 + 1
    facts = [
        f"대회: {match.league}" + (f" ({match.stage})" if match.stage else ""),
        f"대진: {match.team_a.name} ({match.team_a.acronym}) 대 {match.team_b.name} ({match.team_b.acronym})",
        f"방식: {match.best_of}전 {need}선승제",
    ]
    return facts + _context_facts(match, ctx, "현재")


# ---- 검증 도구 ----


def _numbers(text: str, team_names: list[str]) -> set[str]:
    for name in sorted(team_names, key=len, reverse=True):
        text = text.replace(name, " ")
    return set(re.findall(r"\d+", text))


def check_text(lines: list[str], facts: list[str], match: Match) -> list[str]:
    """팩트에 없는 숫자, 금지어를 찾는다. 문제가 없으면 빈 목록."""
    names = [match.team_a.name, match.team_b.name, match.team_a.acronym, match.team_b.acronym]
    allowed = _numbers(" ".join(facts), names)
    issues: list[str] = []
    text = " ".join(lines)
    extra = _numbers(text, names) - allowed
    if extra:
        issues.append(f"팩트에 없는 숫자 사용: {', '.join(sorted(extra))}")
    for word in BANNED_WORDS:
        if word in text:
            issues.append(f"금지어 사용: {word}")
    return issues


def check_draft(draft: Draft, facts: list[str], match: Match) -> list[str]:
    issues = check_text([draft.headline, *draft.summary], facts, match)
    winner, loser = match.winner, match.loser
    assert winner and loser
    if winner.name not in draft.headline and winner.acronym not in draft.headline:
        issues.append("헤드라인에 승리 팀이 없음")
    if len(draft.headline) > HEADLINE_MAX:
        issues.append(f"헤드라인이 {HEADLINE_MAX}자를 넘음")
    if len(draft.summary) != 3:
        issues.append("요약이 3줄이 아님")
    if any(len(line) > LINE_MAX for line in draft.summary):
        issues.append(f"요약 문장이 {LINE_MAX}자를 넘음")
    # 패배 팀을 승자로 적는 가장 흔한 오류를 잡는다.
    for token in (loser.name, loser.acronym):
        if re.search(rf"{re.escape(token)}\s*(승리|완승|신승|역전승)", draft.headline):
            issues.append("헤드라인이 패배 팀을 승자로 표현함")
            break
    return issues
