# 협곡 브리핑

LoL e스포츠 경기 결과를 세 줄로 요약하고, 세트별 밴픽·교전·선수 기록과 밴픽 예측을 함께 보여 주는 사이트입니다. 역할이 나뉜 에이전트들이 자료를 모으고, 분석하고, 요약을 쓰고, 사실 여부를 다시 확인합니다. 서버 없이 GitHub Actions와 GitHub Pages만으로 돌아갑니다.

지금 상태와 남은 일, 모델 검증 수치는 [BACKLOG.md](BACKLOG.md)에 있습니다.

## 화면 구성

| 페이지 | 내용 |
|---|---|
| 홈 | 주요 경기, 대회 대진표(라운드별 진출·탈락), 진행 중인 경기, 리그 현황, 다음 경기, 최근 결과(팀 필터) |
| 리그 일정 | 현재 시즌의 예정·진행 중 경기와 지난 경기 |
| 예정 경기 | 양 팀 입장의 근거와 관전 포인트 |
| 팀 전적 | 스테이지별 승패, 세트 득실, 최근 5경기, 연승·연패 |
| 대회 규칙 | 대회별 진행 순서와 진출 조건 (LCK, MSI, 월즈, 스위스 스테이지) |
| 밴픽·용어 | 밴픽 순서와 피어리스·첫 번째 선택권, 용어 설명 |
| 경기 상세 | 요약, 세트별 밴픽·승률·기록·골드 흐름·킬 위치·정글 동선·선수 맞대결과 평점, 밴픽 예상과 실제, 경기 전 AI 모의 밴픽 |
| 밴픽 예측 | 패치별 메타, 예측 적중률, 다가오는 경기의 예상 밴픽, AI 모의 밴픽, 지난 시리즈별 적중 |

## 구조

```
GitHub Actions
  ├─ archive (하루 네 번)
  │    └─ python -m pipeline.collect      자료 수집: 경기·밴픽·선수 기록·타임라인·주최 측 선정 선수, 챔피언 이름표·아이콘, 팀 로고, 평점 의견, (키가 있으면) 공식 채널 영상
  └─ pipeline (매시 17분) / archive 뒤
       └─ python -m pipeline.run
            ├─ 리그 집계: 시즌 일정, 스테이지별 팀 전적, 대진표
            ├─ 브리핑 그래프: 수집 → 분석 → 작성 → 검증 ─ 통과 → 편집 → 저장
            │                              ↑        └ 반려 → 재작성 (최대 2회, 넘으면 템플릿)
            ├─ 프리뷰 그래프: 수집 → (A측 패널 ∥ B측 패널) → 사회자 → 편집 → 저장
            └─ 분석(pipeline/analysis.py)
                 ├─ 밴픽 예측: 그 패치의 공식 경기 기록으로 예상 → 실제와 비교 (세트마다 갱신)
                 ├─ 패치별 메타: 패치마다 많이 나온 챔피언, 직전 패치 대비 변화
                 ├─ 선수 평점: 세트 기록으로 계산한 10점 만점 점수에 팬 의견을 일부 반영
                 ├─ 승률: 밴픽 전/후 (Elo + 진영 + 조합), 전진 검증
                 ├─ 경기 후 분석: 교전, 오브젝트, 골드 흐름, 정글 동선, 선수 맞대결
                 └─ 모의 밴픽 그래프: 팀 에이전트 ⇄ 팀 에이전트 (20수) → 해설
                      │
                      └─ data/ 커밋 → Next.js 정적 빌드 → GitHub Pages
```

| 에이전트 | 하는 일 | 구현 |
|---|---|---|
| 수집 | 끝난 경기, 예정 경기, 두 팀의 최근 전적과 맞대결 기록 조회 | PandaScore API, 코드 |
| 분석 | 풀세트·역전·연승 저지 같은 특징 도출, 경기 관점 선택 | 규칙 + LLM |
| 작성 | 헤드라인과 요약 세 줄 작성 | LLM (실패 시 템플릿) |
| 검증 | 요약의 숫자·승패를 데이터와 대조, 문제가 있으면 반려 | 코드 검사 + LLM 팩트체커 |
| 편집 | 결승·플레이오프 여부, 순위, 경기 특징으로 주요 경기 점수 부여 | 규칙 |
| 패널 A/B | 예정 경기에서 각 팀 입장의 근거 제시 (병렬 실행) | LLM (실패 시 템플릿) |
| 사회자 | 양측 주장을 중립적인 관전 포인트로 정리 | LLM (실패 시 템플릿) |
| 팀 에이전트 ×2 | 모의 밴픽에서 한 팀씩 맡아, 예측 모델이 낸 후보 중 하나를 골라 번갈아 둠 | LLM (없으면 1순위 후보) |
| 해설 | 끝난 모의 밴픽의 관전 포인트 정리 | LLM (없으면 템플릿) |

LLM이 쓴 문장은 코드가 먼저 걸러 냅니다. 데이터에 없는 숫자가 나오거나 패배 팀을 승자로 적으면 작성 단계로 되돌아가고, 한도를 넘으면 규칙으로 만든 문장으로 바꿉니다. LLM 키가 없거나 호출이 실패해도 사이트는 템플릿 문장으로 계속 갱신됩니다.

## 기술 스택

- 파이프라인: Python 3.12, LangGraph, LangChain(`init_chat_model`), Pydantic
- 사이트: Next.js(App Router, 정적 export), TypeScript
- 운영: GitHub Actions(예약 실행·배포), GitHub Pages
- 모델: 패치 단위 빈도 기반 밴픽 예측, Elo + 로지스틱 회귀 승률 (외부 ML 라이브러리 없이 직접 구현, 시간순 검증)
- LLM: `LLM_MODEL=제공사:모델` 하나로 Anthropic / Google / OpenAI / Ollama 전환
- 데이터: Leaguepedia 공개 API(경기·밴픽·선수 기록·타임라인), Riot Data Dragon(챔피언 이름·아이콘), lolesports 공식 이미지 서버(팀 로고), PandaScore API(실시간 일정, 선택)

## 데이터 모드

토큰과 파일 유무에 따라 세 가지로 돕니다.

| 모드 | 조건 | 데이터 |
|---|---|---|
| live | `PANDASCORE_TOKEN` 이 있음 | PandaScore API 로 매시 갱신 |
| archive | 토큰이 없고 `data/archive/*.json` 이 있음 | Leaguepedia 시즌 기록, 하루 네 번 자동 갱신 |
| sample | 둘 다 없음 | 가상 팀 샘플 |

시즌 기록은 `archive` 워크플로가 하루 네 번 Leaguepedia 공개 API 에서 받아 옵니다 (LCK, 퍼스트 스탠드, MSI, 월즈). 수동 실행도 됩니다. 수집원은 `pipeline/collect.py` 에 등록하고, 수집 결과는 `data/collect.json` 에 남습니다. 원본 행은 `data/raw/` 에 남기 때문에, 스테이지 이름 같은 정리 규칙을 고친 뒤에는 `python -m pipeline.leaguepedia --year 2026 --offline` 으로 네트워크 없이 다시 정리할 수 있습니다. Leaguepedia 의 내용은 CC BY-SA 이므로 사이트 꼬리말에 출처를 표기합니다.

## 로컬에서 실행

```bash
# 파이프라인 (키 없이 실행하면 가상 팀 샘플 데이터 + 템플릿 문장)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
python -m pipeline.run

# 실제 데이터와 LLM 사용
cp .env.example .env        # 값 채우기
set -a; source .env; set +a
python -m pipeline.run

# 사이트
cd web
npm install
npm run dev                 # http://localhost:3000
```

## 코드 규칙과 검사

CI(`.github/workflows/ci.yml`)가 푸시마다 아래를 모두 돌립니다. 올리기 전에 같은 명령으로 확인합니다.

| 대상 | 명령 | 내용 |
|---|---|---|
| 파이프라인 | `ruff check .` | 린트 (규칙은 `pyproject.toml`) |
| | `ruff format .` | 포맷 (한 줄 120자) |
| | `python -m pytest -q` | 테스트 (네트워크·API 키 없이 돈다) |
| 사이트 | `npm run check` | 타입 검사, ESLint(Next.js 권장 규칙), Prettier 포맷 검사 |
| | `npm run format` | Prettier 로 포맷 |
| | `npm run build` | 정적 빌드 |

작성 원칙

- 데이터 형식은 파이프라인의 `pipeline/schemas.py`·`pipeline/analysis.py` 와 사이트의 `web/lib/types.ts` 가 짝을 이룹니다. 한쪽을 바꾸면 다른 쪽도 바꿉니다.
- 평점 의견 이슈의 형식은 `web/lib/feedback.ts`(만드는 쪽)와 `pipeline/feedback.py`(읽는 쪽)가 짝입니다.
- 사이트는 빌드 때 `data/` 를 읽는 정적 사이트입니다. 화면 컴포넌트는 데이터를 바로 쓰지 않고 `web/lib/sets.ts` 같은 변환을 거친 값을 받습니다(진영이 아니라 왼쪽·오른쪽 팀 기준).
- 주석과 문서는 한국어로, 왜 그렇게 했는지를 적습니다.

## 배포 설정

1. 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 바꿉니다.
2. **Settings → Secrets and variables → Actions**에 값을 넣습니다.

   | 종류 | 이름 | 값 |
   |---|---|---|
   | Secret | `PANDASCORE_TOKEN` | PandaScore 대시보드의 액세스 토큰 |
   | Secret | `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `OPENAI_API_KEY` | 쓰는 제공사 하나만 |
   | Variable | `LLM_MODEL` | `제공사:모델명` (예: `anthropic:claude-haiku-5-5`) |
   | Variable (선택) | `OLLAMA_BASE_URL` | `LLM_MODEL=ollama:<모델>` 일 때 Ollama 서버 주소 |
   | Secret (선택) | `YOUTUBE_API_KEY` | 공식 채널 영상 목록 수집 (명장면 링크용) |
   | Variable (선택) | `HIGHLIGHT_LINKS`, `HIGHLIGHT_OFFSET_SEC` | 명장면 링크 노출(`1`)과 중계 지연 보정(초). 켜는 순서는 BACKLOG.md |
   | Secret (선택) | `GRID_API_KEY` | 실시간 밴픽 (연결부 구현 전) |
   | Variable (선택) | `LEAGUES` | 리그 이름, 쉼표 구분 |
   | Variable (선택) | `PANDASCORE_LEAGUE_IDS` | 리그 ID를 직접 지정할 때 |

3. **Actions** 탭에서 `pipeline` 워크플로를 한 번 수동 실행합니다. 로그의 `리그 'LCK' → ...` 줄에서 리그가 제대로 잡혔는지 확인합니다.
4. 사이트 주소는 `https://<계정>.github.io/<레포명>/`입니다.

토큰을 넣기 전에는 샘플 데이터가 올라가고, 화면 위에 샘플이라는 안내가 붙습니다.

## 폴더

```
pipeline/            멀티에이전트 파이프라인
  agents/            에이전트 노드와 프롬프트 (brief, preview, mock_draft)
  graphs.py          LangGraph 그래프 정의
  facts.py           규칙 기반 팩트 도출과 검증 도구
  leagues.py         리그 일정·팀 전적 집계, 주요 경기 점수
  pandascore.py      API 클라이언트
  collect.py         자동 수집 진입점 (수집원 등록, 상태 기록)
  leaguepedia.py     시즌 기록·밴픽·선수 기록·타임라인 수집과 정리
  champions.py       챔피언 한국어 이름표와 아이콘 주소
  logos.py           팀 로고 주소
  ratings.py         세트별 선수 평점 (가중치는 ratings.config.json)
  feedback.py        평점에 대한 팬 의견 수집(GitHub 이슈)과 집계
  awards.py          대회 종료 후 발표되는 상(awards.json)을 결승 경기에 잇기
  youtube.py         공식 채널 영상 목록과 방송 시각
  gamedata.py        세트 기록 모델 (밴픽 순서, 진영, 오브젝트, 선수 기록)
  draft_model.py     밴픽 예측과 시간순 검증
  win_model.py       밴픽 전/후 승률과 전진 검증
  insights.py        교전, 오브젝트, 골드 흐름, 정글 동선, 선수 맞대결
  highlights.py      킬 장면의 영상 위치 계산
  live.py            실시간 밴픽 추적 뼈대 (수동 피드, GRID 자리)
  analysis.py        위 모듈을 묶어 사이트용 파일 생성 (입력 → 밴픽 예측 → 승률 → 평점 → 파일)
  archive.py         받아 둔 시즌 기록을 읽는 데이터 소스
  sample.py          키 없이 돌릴 때 쓰는 가상 팀 데이터
  store.py           data/*.json 저장
tests/               네트워크·키 없이 도는 테스트
data/                파이프라인 결과 (사이트가 빌드 때 읽음)
web/                 Next.js 사이트
  app/               페이지 (홈, 일정, 예정 경기, 팀 전적, 밴픽 예측, 규칙, 용어, 경기 상세)
  components/        화면 조각. match/(경기 상세), sets/(세트별 기록), draft/(밴픽 예측 페이지)
  lib/               data.ts(데이터 읽기), types.ts(데이터 형식), sets.ts(세트 화면 변환),
                     official.ts(주최 측 선정 선수 표기), feedback.ts(평점 의견 주소), format.ts(날짜·비율)
  content/           대회 규칙(tournaments.ts)과 밴픽·용어(terms.ts). 시즌이 바뀌면 여기를 고친다
ratings.config.json  평점 가중치와 팬 의견 반영 정도
awards.json          대회 종료 후 상(파이널 MVP 등). 보도로 확인한 것만 출처와 함께 적는다
pyproject.toml       파이프라인 코드 규칙(ruff)
.github/workflows/   pipeline(예약 실행), archive(자료 수집), deploy(Pages), ci(린트·테스트·빌드)
.github/actions/     워크플로가 함께 쓰는 단계(바뀐 데이터 커밋)
```

## 알아 둘 제약

- GitHub Pages는 정적 호스팅입니다. 로그인, 결제, 서버 API는 올릴 수 없고, GitHub는 Pages를 상업적 SaaS 운영 용도로 쓰는 것을 허용하지 않습니다. 수익화를 하려면 호스팅을 옮겨야 합니다.
- 예약 실행은 늦어지거나 건너뛸 수 있어 실시간 중계 용도로는 맞지 않습니다. 경기 종료 후 최대 1~2시간 안에 올라오는 정도로 보면 됩니다.
- 공개 저장소는 60일 동안 활동이 없으면 예약 워크플로가 꺼집니다. 파이프라인이 주 1회 `data/meta.json`을 갱신해 이를 막습니다.
- 진행 중인 경기 표시는 마지막 실행 시점 기준입니다. 정적 사이트라 실시간으로 바뀌지 않습니다.
- 팀 전적표는 승수와 세트 득실만으로 정렬합니다. 상대 전적·타이브레이커는 반영하지 않아 공식 순위와 다를 수 있습니다.
- 대회 규칙과 밴픽·용어는 2026 시즌 기준으로 직접 정리한 요약입니다. 새 시즌 규정이 나오면 손으로 갱신해야 합니다.
- 밴픽 예측과 승률은 재미로 보는 참고용입니다. 올해 기록으로 잰 적중률은 BACKLOG.md 에 있고, 픽 예측과 조합 효과는 약합니다.
- 세트 상세·예측은 Leaguepedia 기록이 있는 archive 모드에서만 만들어집니다. live 모드(PandaScore 무료 플랜)에는 챔피언·킬·선수 기록이 없습니다.
- PandaScore 약관과 Riot Games의 팬 콘텐츠 정책은 공개 운영 전에 직접 확인하세요. 팀 로고는 각 팀의, 챔피언 이미지는 Riot Games 의 자산이며 공식 이미지 서버의 그림을 불러와 표시합니다. 이 사이트는 Riot Games 가 보증하거나 후원하지 않는 팬 사이트입니다. 베팅·배당 관련 내용은 다루지 않습니다.
