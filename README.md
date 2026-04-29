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

## 데이터 사용법

### raw URL로 직접 다운로드

```bash
# 전체 최신 스냅샷 (1회 다운로드용, 약 5,700행)
curl -O https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv

# 특정 월 데이터
curl -O https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/2026/04.csv
```

### pandas로 읽기

```python
import pandas as pd

# 최신 스냅샷 — code 컬럼은 반드시 string으로 읽어야 zero-pad("00060")가 보존됩니다.
df = pd.read_csv(
    "https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv",
    dtype={"code": str},
)

# 특정 월
df_april = pd.read_csv(
    "https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/2026/04.csv",
    dtype={"code": str},
)

# 24시간 운영 매장만 필터
df_24h = df[df["is_24h"] == 1]

# 와인+커피 동시 제공 매장
df_wc = df[(df["svc_wine"] == 1) & (df["svc_coffee"] == 1)]
```

### git clone으로 시계열 분석

```bash
git clone https://github.com/itda-skills/data-retail.git
cd data-retail

# 특정 매장의 정보 변경 이력
git log --all -p -- emart24/_latest.csv | grep "00060"
```

## AI 어시스턴트(Claude / ChatGPT 등) 활용 가이드

이 데이터셋은 **AI 에이전트가 즉시 소비 가능한 형태**로 설계되었습니다 — 별도 인증 없이 raw URL 한 줄로 접근할 수 있고, 컬럼이 명시적으로 정의되어 있어 LLM의 코드 생성 정확도가 높습니다.

### 1. 컨텍스트 주입용 프롬프트 템플릿

Claude / ChatGPT / Cursor 등 AI 어시스턴트에게 다음 블록을 컨텍스트로 제공하세요:

```
You have access to an open dataset of South Korean emart24 convenience store locations
maintained at https://github.com/itda-skills/data-retail (weekly auto-updated).

Data sources (UTF-8, RFC 4180 CSV, LF):
- Full snapshot:  https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv
                  (~5,700 rows, 27 columns, sorted by code ASC)
- Monthly files:  emart24/{YYYY}/{MM}.csv  (each store appears once in its OPEN_DATE month)
- Schema:         emart24/README.md  (column definitions and service flag meanings)
- Changelog:      emart24/CHANGELOG.md  (weekly diff digest)

CRITICAL when loading:
- Always read the `code` column as string (5-digit zero-padded; integer parsing breaks it).
- `lat` / `lng` are floats. `open_date` is ISO YYYY-MM-DD. `end_date` is "" if active.
- 12 service flags are 0/1 columns prefixed `svc_*` (parcel, atm, wine, coffee, smoothie,
  apple, toto, auto, pickup, chicken, noodle) plus `tobacco_license`.
- `is_24h` = 1 means store is 24-hour operation.

License: data CC-BY-NC-4.0, scripts MIT. Original copyright belongs to emart24 Inc.
```

### 2. Claude Code MCP / 컨텍스트 활용

Claude Code 또는 Claude Desktop에서 `/add-dir` 또는 MCP filesystem 서버로 이 레포를 추가한 뒤, 다음과 같이 자연어로 분석 가능합니다:

- "서울 강남구에 있는 24시간 운영 매장을 lat/lng와 함께 알려줘"
- "지난 분기 신규 오픈한 매장 추세를 월별 막대그래프로 그려줘"
- "와인 + ATM 동시 제공 매장의 지역 분포를 히트맵으로 보여줘"

### 3. 변경 이력 기반 시계열 질의

`git log emart24/_latest.csv` 의 diff가 곧 매주 변경 다이제스트입니다. AI에게 다음과 같이 요청할 수 있습니다:

- "git diff HEAD~4 emart24/_latest.csv 결과를 분석해서 최근 한 달간 신규 매장 목록을 정리해줘"
- "특정 매장 코드의 서비스 변경 이력을 추적해줘"

### 4. RAG / 벡터 인덱싱

각 매장 row를 `{title} {address} {svc_*}` 텍스트로 합쳐 임베딩하면, 자연어 매장 검색 시스템(예: "공항 근처 24시간 와인 파는 곳")을 즉시 구축할 수 있습니다. `emart24/_latest.csv` 를 단일 소스로 사용하세요.

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
