# data-retail

국내 편의점 체인 매장 데이터를 GitHub Actions로 주 1회 자동 수집·공개하는 오픈 데이터 저장소입니다.

[![Weekly emart24 Fetch](https://github.com/itda-skills/data-retail/actions/workflows/weekly-emart24.yml/badge.svg)](https://github.com/itda-skills/data-retail/actions/workflows/weekly-emart24.yml)

> 본 프로젝트는 **[스킬.잇다](https://itda.work)** 에서 만들었습니다. 스킬·Claude 자동화 개발/교육 문의는 **dev@itda.work** 로 보내주세요.

## 현재 수집 체인

| 체인 | 디렉터리 | 갱신 주기 | 매장 수 |
|------|---------|---------|--------|
| emart24 | `emart24/` | 주 1회 (월 03:00 KST) | ~5,700 |

## 데이터 라이선스

본 데이터는 **emart24 공식 점포찾기 API**에서 자동 수집된 가공물이며,
**원본 저작권은 이마트24(주)에 있습니다.**

- 데이터: **CC-BY-NC-4.0** (비상업적 사용, 출처 표시 조건)
- 스크립트 (`scripts/`): **MIT** (자유롭게 사용 가능)
- 상업적 활용은 이마트24에 직접 문의하시기 바랍니다.

## robots.txt 메모

`https://emart24.co.kr/robots.txt` 확인 결과: `/api1/` 경로에 대한 Disallow 규칙이 없습니다.
본 수집기는 공개 API를 대상으로 0.5초 throttle을 적용하며, 주 1회만 실행합니다.

## 데이터 접근

- **전체 스냅샷**: `https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv` (약 5,700행, 27 컬럼, `code` ASC 정렬)
- **월별 파일**: `https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/{YYYY}/{MM}.csv` (한 매장은 본인의 `open_date` 연·월 파일에 1회만 등장)
- **변경 이력**: `git clone` 후 `git log emart24/_latest.csv` — 매주 자동 커밋된 diff 가 시계열 변경 기록입니다.

## AI 어시스턴트(Claude / ChatGPT 등) 활용 지침

이 데이터셋은 **AI 에이전트가 즉시 소비 가능한 형태**로 설계되었습니다 — 별도 인증 없이 raw URL 한 줄로 접근할 수 있고, 컬럼이 명시적으로 정의되어 있어 LLM의 코드 생성 정확도가 높습니다.

### 1. AI에게 데이터를 안내하는 컨텍스트 블록

Claude / ChatGPT / Cursor 등에 아래 블록을 그대로 붙여넣어 컨텍스트로 제공하세요.

```
당신은 itda-skills/data-retail 오픈 데이터셋(주간 자동 갱신)에 접근할 수 있다.
이 데이터는 한국 emart24 편의점 매장 정보다.

데이터 위치 (UTF-8, RFC 4180 CSV, LF 개행):
- 전체 스냅샷: https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv
              (약 5,700행, 27 컬럼, code 오름차순 정렬)
- 월별 파일:   emart24/{YYYY}/{MM}.csv (각 매장은 본인의 OPEN_DATE 월 파일에 1회만 등장)
- 컬럼 정의:   emart24/README.md
- 변경 다이제스트: emart24/CHANGELOG.md

데이터 로드 시 반드시 지킬 것:
- code 컬럼은 항상 문자열로 읽는다. 5자리 zero-pad("00060")이며, 정수로 변환하면 손상된다.
- lat / lng 는 float, open_date 는 ISO YYYY-MM-DD, end_date 는 빈 문자열이면 영업 중이다.
- svc_* (12종: parcel, atm, wine, coffee, smoothie, apple, toto, auto, pickup, chicken,
  noodle) 와 tobacco_license 는 0/1 컬럼이다.
- is_24h = 1 이면 24시간 운영 매장이다.

라이선스: 데이터 CC-BY-NC-4.0, 스크립트 MIT. 원본 저작권은 이마트24(주)에 귀속된다.
```

### 2. Claude Code / Claude Desktop 에서의 활용

Claude Code 의 `/add-dir` 또는 MCP filesystem 서버로 이 레포를 추가한 뒤, 자연어로 다음과 같이 분석을 요청할 수 있습니다.

- "서울 강남구에 있는 24시간 운영 매장을 위경도와 함께 알려줘"
- "지난 분기 신규 오픈한 매장 추세를 월별 막대그래프로 그려줘"
- "와인과 ATM 을 동시에 제공하는 매장의 지역 분포를 보여줘"

### 3. 변경 이력 기반 시계열 질의

`git log emart24/_latest.csv` 의 diff 가 곧 매주 변경 다이제스트입니다. 다음과 같이 요청해 보세요.

- "최근 한 달간 emart24/_latest.csv 의 git diff 를 분석해서 신규 매장 목록을 정리해줘"
- "특정 매장 코드의 서비스 플래그 변경 이력을 추적해줘"
- "지난 6개월간 폐점 추정(last_seen_at 갱신 중단) 매장을 찾아줘"

### 4. RAG / 벡터 인덱싱

각 매장 행을 `{title} {address} {svc_*}` 텍스트로 합쳐 임베딩하면, 자연어 매장 검색 시스템(예: "공항 근처 24시간 와인 파는 곳") 을 즉시 구축할 수 있습니다. `emart24/_latest.csv` 를 단일 소스로 사용하세요.

## 디렉터리 구조

```
emart24/
├── README.md          # 컬럼 정의, 서비스 플래그 의미
├── CHANGELOG.md       # 주간 변경 다이제스트 (사람이 읽기용)
├── _latest.csv        # 전체 매장 스냅샷 (매주 재작성, ~5,700행, 27 컬럼)
├── 2008/
│   ├── 01.csv         # 2008년 1월 오픈 매장
│   └── ...
└── 2026/
    ├── 04.csv
    └── 05.csv         # 예정 오픈 매장 포함 가능
```

## CSV 컬럼 요약

총 26개 (월별 CSV) 또는 27개 (`_latest.csv` 는 `current_month_file` 추가). 자세한 정의는 [`emart24/README.md`](emart24/README.md) 참조.

핵심 컬럼: `code`, `title`, `address`, `lat`, `lng`, `open_date`, `end_date`, `start_hhmm`, `end_hhmm`, `is_24h`, `svc_*` (12종), `tobacco_license`, `first_seen_at`, `last_seen_at`.

## 알려진 한계

- 매장 폐점 추적은 `last_seen_at` 컬럼으로 근사값만 제공됩니다 (상세 추적은 후속 SPEC).
- 예정 오픈 매장(`open_date > 오늘`)이 실제로 오픈하지 않을 수 있습니다.
- API 구조 변경 시 수집이 중단될 수 있습니다. 이슈를 통해 알려주세요.

## 후속 체인 (예약)

GS25, CU, 7-Eleven, 미니스톱 — 동일 디렉터리 패턴으로 추가될 예정입니다.

## 기여

- SPEC 문서: `.moai/specs/SPEC-EMART24-001/spec.md`
- 후속 체인 추가, 버그 제보, 데이터 활용 사례는 이슈 또는 PR을 통해 기여해 주세요.

## 만든 곳

본 프로젝트는 **[스킬.잇다 (itda.work)](https://itda.work)** 에서 운영합니다.

- 스킬·Claude 자동화 개발 문의: **dev@itda.work**
- 사내 교육·워크숍 문의: **dev@itda.work**
- 데이터 활용 사례 공유 환영합니다.
