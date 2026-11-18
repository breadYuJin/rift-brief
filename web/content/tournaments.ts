// 대회 진행 방식. 대회 하나가 탭 하나다. 시즌이 바뀌면 이 파일만 고치면 된다.
// 공식 발표와 보도를 바탕으로 직접 정리한 요약이며, 정확한 조항은 출처의 원문을 따른다.

export const CHECKED = "2026년 11월 16일 확인";

export interface Stage {
  name: string;
  teams: string;
  format: string;
  outcome: string;
}

export interface Note {
  term: string;
  body: string;
}

export interface Source {
  title: string;
  url: string;
}

export interface Tournament {
  slug: "lck" | "msi" | "worlds" | "swiss";
  tab: string;
  title: string;
  season: string;
  lede: string;
  facts: { label: string; value: string }[];
  stagesTitle?: string;
  stages: Stage[];
  notesTitle?: string;
  notes: Note[];
  sources: Source[];
}

export const TOURNAMENTS: Tournament[] = [
  {
    slug: "lck",
    tab: "LCK",
    title: "LCK",
    season: "2026 시즌 기준",
    lede: "한국 리그입니다. 한 해는 LCK컵으로 시작해 정규 시즌, 플레이-인, 플레이오프 순서로 이어집니다. 2027 시즌 운영 방식은 아직 발표되지 않았습니다.",
    facts: [
      { label: "참가", value: "10개 팀" },
      { label: "정규 시즌 경기", value: "주로 3전 2선승제" },
      { label: "플레이-인·플레이오프", value: "5전 3선승제" },
    ],
    stagesTitle: "한 해의 진행 순서",
    stages: [
      {
        name: "LCK컵",
        teams: "10개 팀, 바론 그룹과 장로 그룹",
        format: "상대 그룹 팀과 맞붙는 그룹 대항전 뒤 플레이-인, 플레이오프",
        outcome: "성적 상위 팀이 시즌 첫 국제 대회인 퍼스트 스탠드에 나갑니다.",
      },
      {
        name: "정규 시즌 1~2라운드",
        teams: "10개 팀",
        format: "모든 팀이 서로 두 번씩 만나는 풀리그",
        outcome:
          "상위 5개 팀은 레전드 그룹, 하위 5개 팀은 라이즈 그룹에 들어갑니다. 상위 6개 팀은 MSI 대표 선발전에 나갑니다.",
      },
      {
        name: "정규 시즌 3~4라운드",
        teams: "레전드 그룹 5팀, 라이즈 그룹 5팀",
        format: "같은 그룹끼리만 맞붙는 풀리그",
        outcome:
          "레전드 1~4위는 플레이오프 직행, 레전드 5위와 라이즈 1~3위는 플레이-인, 라이즈 4·5위는 시즌 종료입니다.",
      },
      {
        name: "플레이-인",
        teams: "4개 팀",
        format: "레전드 5위와 라이즈 1위가 먼저 붙고, 라이즈 2·3위의 승자가 앞 경기 패자와 최종전",
        outcome: "첫 경기 승자와 최종전 승자, 두 팀이 플레이오프에 올라갑니다.",
      },
      {
        name: "플레이오프",
        teams: "6개 팀",
        format: "1라운드부터 더블 엘리미네이션. 한 번 져도 패자조에서 기회가 한 번 더 있습니다.",
        outcome: "우승 팀을 가리고, 최종 성적으로 월드 챔피언십 출전 팀과 시드를 정합니다.",
      },
    ],
    notesTitle: "순위와 탈락 확정",
    notes: [
      {
        term: "순위를 매기는 순서",
        body: "시즌 중 순위는 승률이 먼저이고, 같으면 세트 득실을 봅니다. 최종 순위에서도 가려지지 않으면 동률인 팀끼리의 상대 전적을 따지고, 그래도 같으면 타이브레이커 경기를 치릅니다. 2025 규정집 기준입니다.",
      },
      {
        term: "탈락 확정을 판단하는 법",
        body: "남은 경기를 모두 이겨도 커트라인에 있는 팀의 현재 승수에 닿지 못하면 탈락이 확정됩니다. 커트라인 팀이 이미 10승인데 내 팀이 6승에 3경기를 남겼다면 최대 9승이라 확정 탈락입니다.",
      },
      {
        term: "경우의 수가 남는 때",
        body: "남은 경기를 다 이겼을 때 승수가 같아질 수 있다면 아직 확정이 아닙니다. 세트 득실과 상대 전적으로 갈리기 때문에 다른 팀 결과까지 봐야 합니다. 진출 확정은 반대로, 아래 팀들이 남은 경기를 다 이겨도 내 현재 승수를 넘지 못할 때입니다.",
      },
      {
        term: "이 사이트의 전적표",
        body: "팀 전적 페이지는 승수와 세트 득실만으로 정렬합니다. 상대 전적과 타이브레이커는 반영하지 않아 공식 순위와 다를 수 있습니다.",
      },
    ],
    sources: [
      {
        title: "LoL Esports, 2026 LCK 진행 방식 안내",
        url: "https://lolesports.com/ko-KR/news/2026-lck-format-explainer",
      },
      { title: "한국경제, 2026년 LCK 운영 방안 공개", url: "https://www.hankyung.com/article/202511067533i" },
      {
        title: "LoL Esports, 2025 LCK 규정집 개정 안내",
        url: "https://lolesports.com/ko-KR/news/2025-lck-rule-book-update",
      },
    ],
  },
  {
    slug: "msi",
    tab: "MSI",
    title: "미드 시즌 인비테이셔널 (MSI)",
    season: "2026년 대회 기준",
    lede: "시즌 중반에 각 지역 상위 팀이 모이는 국제 대회입니다. 2026년에는 대전에서 열렸고, 모든 경기를 5전 3선승제로 치렀습니다.",
    facts: [
      { label: "참가", value: "6개 지역 11개 팀" },
      { label: "경기 방식", value: "전 경기 5전 3선승제" },
      { label: "LCK 출전", value: "대표 선발전 1·2위" },
    ],
    stagesTitle: "진행 순서",
    stages: [
      {
        name: "플레이-인 스테이지",
        teams: "4개 팀 (브래킷에 직행하지 못한 2번 시드)",
        format: "더블 엘리미네이션. 두 번 지면 탈락합니다.",
        outcome: "한 팀만 브래킷 스테이지에 올라갑니다.",
      },
      {
        name: "브래킷 스테이지",
        teams: "8개 팀 (직행 7팀 + 플레이-인 통과 1팀)",
        format: "더블 엘리미네이션. 승자조에서 져도 패자조로 내려가 한 번 더 싸웁니다.",
        outcome: "우승 팀이 월드 챔피언십 출전권을 얻습니다.",
      },
    ],
    notesTitle: "알아 둘 규칙",
    notes: [
      {
        term: "브래킷 직행 조건",
        body: "각 지역 1번 시드는 브래킷 스테이지로 바로 갑니다. 그해 퍼스트 스탠드에서 우승한 지역은 2번 시드도 함께 직행합니다.",
      },
      {
        term: "지역별 출전 수",
        body: "LCK, LPL, LEC, LCS, LCP는 두 팀씩, CBLOL은 한 팀이 나옵니다.",
      },
      {
        term: "성적에 걸린 것",
        body: "우승 팀은 월드 챔피언십에 직행하고, 준우승 팀이 속한 지역은 월드 챔피언십 시드를 하나 더 받습니다.",
      },
    ],
    sources: [
      {
        title: "LoL Esports, 2026 MSI 대회 개요",
        url: "https://lolesports.com/ko-KR/tournament/115570934354631452/overview",
      },
      {
        title: "LoL Esports, MSI와 월드 챔피언십 진행 방식 안내",
        url: "https://lolesports.com/ko-KR/news/msi-and-worlds-updates",
      },
    ],
  },
  {
    slug: "worlds",
    tab: "월즈",
    title: "월드 챔피언십 (월즈)",
    season: "2026년 대회 기준",
    lede: "한 해를 마무리하는 가장 큰 국제 대회입니다. 플레이-인, 스위스 스테이지, 토너먼트 순서로 팀을 줄여 갑니다.",
    facts: [
      { label: "참가", value: "19개 팀" },
      { label: "스위스 스테이지", value: "16개 팀 중 8개 팀 통과" },
      { label: "토너먼트", value: "8강부터 5전 3선승제" },
    ],
    stagesTitle: "진행 순서",
    stages: [
      {
        name: "플레이-인 스테이지",
        teams: "4개 팀",
        format: "5전 3선승제 더블 엘리미네이션",
        outcome: "한 팀이 스위스 스테이지에 합류합니다.",
      },
      {
        name: "스위스 스테이지",
        teams: "16개 팀",
        format: "승패가 같은 팀끼리 맞붙어 3승이면 통과, 3패면 탈락",
        outcome: "3승을 채운 8개 팀이 8강에 올라갑니다.",
      },
      {
        name: "토너먼트 스테이지",
        teams: "8개 팀",
        format: "8강, 4강, 결승. 한 번 지면 탈락하는 5전 3선승제",
        outcome: "결승 승자가 그해 세계 챔피언이 됩니다.",
      },
    ],
    notesTitle: "알아 둘 규칙",
    notes: [
      {
        term: "출전권",
        body: "지역 리그의 최종 성적으로 출전 팀과 시드가 정해집니다. MSI 우승 팀은 직행하고, MSI 준우승 지역은 시드를 하나 더 받습니다.",
      },
      {
        term: "스위스 스테이지",
        body: "조별 리그 대신 쓰는 방식입니다. 자세한 진행은 스위스 스테이지 탭에서 볼 수 있습니다.",
      },
    ],
    sources: [
      {
        title: "LoL Esports, MSI와 월드 챔피언십 진행 방식 안내",
        url: "https://lolesports.com/ko-KR/news/msi-and-worlds-updates",
      },
      {
        title: "한국경제, 2025 월드 챔피언십 스위스 스테이지 안내",
        url: "https://www.hankyung.com/article/202510176055i",
      },
    ],
  },
  {
    slug: "swiss",
    tab: "스위스 스테이지",
    title: "스위스 스테이지",
    season: "월드 챔피언십에서 쓰는 방식",
    lede: "조를 나누지 않고, 매 라운드 승패가 같은 팀끼리 맞붙는 방식입니다. 3승을 먼저 채우면 통과하고 3패를 먼저 당하면 탈락합니다.",
    facts: [
      { label: "참가", value: "16개 팀" },
      { label: "통과 조건", value: "3승" },
      { label: "탈락 조건", value: "3패" },
    ],
    stages: [],
    notesTitle: "규칙",
    notes: [
      {
        term: "대진",
        body: "매 라운드 승패가 같은 팀끼리 추첨으로 상대를 정합니다. 이미 만난 팀과는 다시 붙지 않고, 1라운드에서는 같은 지역 팀끼리 만나지 않습니다.",
      },
      {
        term: "단판과 3전 2선승제",
        body: "기본은 단판입니다. 이기면 통과하거나 지면 탈락하는 경기, 즉 2승 팀과 2패 팀이 치르는 경기만 3전 2선승제입니다.",
      },
      {
        term: "라운드 수",
        body: "길어도 5라운드에서 끝납니다. 3전 전승 팀은 3라운드 만에 통과하고, 2승 2패 팀은 마지막 5라운드 한 경기로 통과와 탈락이 갈립니다.",
      },
      {
        term: "조별 리그와 다른 점",
        body: "성적이 비슷한 팀끼리 계속 만나기 때문에 라운드가 갈수록 실력이 비슷한 대진이 나옵니다. 순위를 따질 필요 없이 3승, 3패로만 결과가 정해져 타이브레이커가 없습니다.",
      },
    ],
    sources: [
      {
        title: "한국경제, 2025 월드 챔피언십 스위스 스테이지 안내",
        url: "https://www.hankyung.com/article/202510148560i",
      },
      { title: "엑스포츠뉴스, 스위스 스테이지 1라운드 대진", url: "https://www.xportsnews.com/article/2064863" },
      { title: "쿠키뉴스, 스위스 스테이지 진행 방식", url: "https://www.kukinews.com/article/view/kuk202410020129" },
    ],
  },
];

export const getTournament = (slug: string) => TOURNAMENTS.find((t) => t.slug === slug);

// 스위스 스테이지 라운드별 전적 조. 16개 팀 기준.
export type SwissKind = "normal" | "advance" | "eliminate" | "both";
export const SWISS_ROUNDS: { round: number; groups: { record: string; teams: number; kind: SwissKind }[] }[] = [
  { round: 1, groups: [{ record: "0승 0패", teams: 16, kind: "normal" }] },
  {
    round: 2,
    groups: [
      { record: "1승 0패", teams: 8, kind: "normal" },
      { record: "0승 1패", teams: 8, kind: "normal" },
    ],
  },
  {
    round: 3,
    groups: [
      { record: "2승 0패", teams: 4, kind: "advance" },
      { record: "1승 1패", teams: 8, kind: "normal" },
      { record: "0승 2패", teams: 4, kind: "eliminate" },
    ],
  },
  {
    round: 4,
    groups: [
      { record: "2승 1패", teams: 6, kind: "advance" },
      { record: "1승 2패", teams: 6, kind: "eliminate" },
    ],
  },
  { round: 5, groups: [{ record: "2승 2패", teams: 6, kind: "both" }] },
];

export const SWISS_KIND_TEXT: Record<SwissKind, string> = {
  normal: "단판",
  advance: "3전 2선승, 이기면 통과",
  eliminate: "3전 2선승, 지면 탈락",
  both: "3전 2선승, 이기면 통과 지면 탈락",
};
