# 협곡 브리핑

LoL e스포츠 경기 결과를 세 줄로 요약해 보여 주는 사이트입니다. 역할이 나뉜 에이전트들이 경기 데이터를 모으고, 분석하고, 요약을 쓰고, 사실 여부를 다시 확인합니다. 서버 없이 GitHub Actions와 GitHub Pages만으로 돌아갑니다.

## 화면 구성

| 페이지 | 내용 |
|---|---|
| 홈 | 주요 경기, 진행 중인 경기, 진행 중인 리그와 상위 전적, 다음 경기, 최근 결과(팀 필터) |
| 리그 일정 | 현재 시즌의 예정·진행 중 경기와 지난 경기 |
| 예정 경기 | 양 팀 입장의 근거와 관전 포인트 |
| 팀 전적 | 스테이지별 승패, 세트 득실, 최근 5경기, 연승·연패 |
| 대회 규칙 | 대회별 진행 순서와 진출 조건 (LCK, MSI, 월즈, 스위스 스테이지) |
| 밴픽·용어 | 밴픽 순서와 피어리스·첫 번째 선택권, 용어 설명 |
| 경기 상세 | 요약, 근거 데이터, 브리핑이 만들어진 과정 |

## 구조

```
GitHub Actions (매시 17분)
  └─ python -m pipeline.run
       ├─ 리그 집계: 현재 시즌 일정, 스테이지별 팀 전적, 진행 중 경기
       ├─ 브리핑 그래프: 수집 → 분석 → 작성 → 검증 ─ 통과 → 편집 → 저장
       │                              ↑        └ 반려 → 재작성 (최대 2회, 넘으면 템플릿)
       └─ 프리뷰 그래프: 수집 → (A측 패널 ∥ B측 패널) → 사회자 → 편집 → 저장
            │
            └─ data/*.json 커밋 → Next.js 정적 빌드 → GitHub Pages
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

LLM이 쓴 문장은 코드가 먼저 걸러 냅니다. 데이터에 없는 숫자가 나오거나 패배 팀을 승자로 적으면 작성 단계로 되돌아가고, 한도를 넘으면 규칙으로 만든 문장으로 바꿉니다. LLM 키가 없거나 호출이 실패해도 사이트는 템플릿 문장으로 계속 갱신됩니다.

## 기술 스택

- 파이프라인: Python 3.12, LangGraph, LangChain(`init_chat_model`), Pydantic
- 사이트: Next.js(App Router, 정적 export), TypeScript
- 운영: GitHub Actions(예약 실행·배포), GitHub Pages
- 데이터: PandaScore API 무료 플랜(일정·결과·팀)

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

## 배포 설정

1. 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 바꿉니다.
2. **Settings → Secrets and variables → Actions**에 값을 넣습니다.

   | 종류 | 이름 | 값 |
   |---|---|---|
   | Secret | `PANDASCORE_TOKEN` | PandaScore 대시보드의 액세스 토큰 |
   | Secret | `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `OPENAI_API_KEY` | 쓰는 제공사 하나만 |
   | Variable | `LLM_MODEL` | `제공사:모델명` (예: `anthropic:claude-haiku-5-5`) |
   | Variable (선택) | `LEAGUES` | 리그 이름, 쉼표 구분 |
   | Variable (선택) | `PANDASCORE_LEAGUE_IDS` | 리그 ID를 직접 지정할 때 |

3. **Actions** 탭에서 `pipeline` 워크플로를 한 번 수동 실행합니다. 로그의 `리그 'LCK' → ...` 줄에서 리그가 제대로 잡혔는지 확인합니다.
4. 사이트 주소는 `https://<계정>.github.io/<레포명>/`입니다.

토큰을 넣기 전에는 샘플 데이터가 올라가고, 화면 위에 샘플이라는 안내가 붙습니다.

## 폴더

```
pipeline/            멀티에이전트 파이프라인
  agents/            에이전트 노드와 프롬프트
  graphs.py          LangGraph 그래프 정의
  facts.py           규칙 기반 팩트 도출과 검증 도구
  leagues.py         리그 일정·팀 전적 집계, 주요 경기 점수
  pandascore.py      API 클라이언트
  sample.py          키 없이 돌릴 때 쓰는 가상 팀 데이터
  store.py           data/*.json 저장
tests/               네트워크·키 없이 도는 테스트
data/                파이프라인 결과 (사이트가 빌드 때 읽음)
web/                 Next.js 사이트
  content/           대회 규칙(tournaments.ts)과 밴픽·용어(terms.ts). 시즌이 바뀌면 여기를 고친다
.github/workflows/   pipeline(예약 실행), deploy(Pages), ci(테스트)
```

## 알아 둘 제약

- GitHub Pages는 정적 호스팅입니다. 로그인, 결제, 서버 API는 올릴 수 없고, GitHub는 Pages를 상업적 SaaS 운영 용도로 쓰는 것을 허용하지 않습니다. 수익화를 하려면 호스팅을 옮겨야 합니다.
- 예약 실행은 늦어지거나 건너뛸 수 있어 실시간 중계 용도로는 맞지 않습니다. 경기 종료 후 최대 1~2시간 안에 올라오는 정도로 보면 됩니다.
- 공개 저장소는 60일 동안 활동이 없으면 예약 워크플로가 꺼집니다. 파이프라인이 주 1회 `data/meta.json`을 갱신해 이를 막습니다.
- 진행 중인 경기 표시는 마지막 실행 시점 기준입니다. 정적 사이트라 실시간으로 바뀌지 않습니다.
- 팀 전적표는 승수와 세트 득실만으로 정렬합니다. 상대 전적·타이브레이커는 반영하지 않아 공식 순위와 다를 수 있습니다.
- 대회 규칙과 밴픽·용어는 2026 시즌 기준으로 직접 정리한 요약입니다. 새 시즌 규정이 나오면 손으로 갱신해야 합니다.
- 무료 플랜 데이터에는 챔피언·킬·선수 기록이 없습니다. 요약도 세트 스코어와 전적 수준에서만 씁니다.
- PandaScore 약관과 Riot Games의 팬 콘텐츠 정책은 공개 운영 전에 직접 확인하세요. 팀 로고는 쓰지 않고 약칭만 표시합니다. 베팅·배당 관련 내용은 다루지 않습니다.
