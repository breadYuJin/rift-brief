"""임시 확인용: Leaguepedia 경기 일정표에 주최 측이 뽑은 선수(MVP/POM)가 들어 있는지 본다."""
from collections import Counter

from pipeline.leaguepedia import LEAGUES, Cargo

cargo = Cargo()
for league, pattern in LEAGUES:
    prefix = pattern.format(year=2026)
    for fields in ("MatchId,Tab,Team1,Team2,Winner,MVP,MVPPoints,DateTime_UTC=Date", "MatchId,Tab,Team1,Team2,Winner,MVP,DateTime_UTC=Date"):
        try:
            rows = cargo.query(tables="MatchSchedule", fields=fields, where=f'OverviewPage LIKE "{prefix}%"', order_by="DateTime_UTC")
        except Exception as exc:
            print(f"[probe] {league} {fields.split(',')[5:7]} 실패: {str(exc)[:160]}")
            continue
        filled = [r for r in rows if (r.get("MVP") or "").strip()]
        print(f"[probe] {league}: 경기 {len(rows)}행, MVP 채워진 경기 {len(filled)}")
        print("[probe]   상위:", Counter(r["MVP"] for r in filled).most_common(8))
        print("[probe]   탭별:", Counter(r["Tab"] for r in filled).most_common(12))
        print("[probe]   비어 있는 탭:", Counter(r["Tab"] for r in rows if not (r.get("MVP") or "").strip()).most_common(12))
        for r in filled[:2] + filled[-3:]:
            print("[probe]   예:", r)
        for r in rows[-2:]:
            print("[probe]   마지막 경기:", r)
        break
