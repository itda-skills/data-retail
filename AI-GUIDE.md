# AI 어시스턴트 활용 지침 — itda-skills/data-retail

> 이 문서는 Claude / ChatGPT / Cursor / Copilot 등 AI 어시스턴트가 본 데이터셋을 정확히 이해하고 활용할 수 있도록 작성된 **AI 전용 가이드**입니다.
> 본 문서는 단일 소스로 관리되며, 다음 URL 들 중 하나로 직접 로드하여 사용하세요:
> - jsDelivr (권장): `https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/AI-GUIDE.md`
> - GitHub raw (폴백): `https://raw.githubusercontent.com/itda-skills/data-retail/main/AI-GUIDE.md`

---

## 0. 데이터셋 정체성

당신은 `itda-skills/data-retail` 오픈 데이터셋(주간 자동 갱신)에 접근할 수 있다. 이 저장소는 **여러 한국 편의점 체인의 매장 정보**를 GitHub Actions 로 주 1회 자동 수집·공개하는 시계열 아카이브다. 각 체인은 자체 디렉터리(`{chain}/`) 를 가지며 동일한 디렉터리 구조와 컬럼 규약을 따른다.

수록 체인은 시간이 지남에 따라 늘어난다. 현재 어떤 체인이 수록되어 있는지는 저장소 루트의 `README.md` "현재 수집 체인" 섹션을 참조하라:
- `https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/README.md`

원본 저작권은 각 체인사에 귀속되며, 데이터는 CC-BY-NC-4.0, 스크립트는 MIT 다.

## 1. 데이터 위치 (UTF-8, RFC 4180 CSV, LF 개행)

각 데이터 파일은 두 가지 호스트로 동일하게 제공된다. 환경에 따라 적절한 호스트를 사용하라.

| 호스트 | URL 패턴 | Content-Type | 권장 환경 |
|---|---|---|---|
| **jsDelivr CDN** (권장) | `https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/{path}` | `text/csv` | Claude.ai web, ChatGPT, 일반 브라우저 fetch |
| **GitHub raw** | `https://raw.githubusercontent.com/itda-skills/data-retail/main/{path}` | `text/plain` (sandbox CSP) | curl, git, Claude Code, 서버측 fetch |

> **Claude.ai web (claude chat) 에서 fetch 가 실패하면 반드시 jsDelivr URL 로 재시도하라.** GitHub raw 응답에 붙은 sandbox CSP 헤더가 일부 브라우저측 fetch 도구에서 차단되는 알려진 이슈가 있다. jsDelivr 는 정상 `text/csv` 를 반환한다. (단, jsDelivr 캐시는 12시간 지연이 있을 수 있다.)

> **[중요] web_fetch 사이즈 제약.** Claude.ai web 의 web_fetch 는 응답 크기 상한이 있어 전체 스냅샷(체인당 수 MB)을 받지 못하고 "Failed to fetch" 로 실패할 수 있다. **이 가이드는 기본적으로 월별 파일(`{YYYY}/{MM}.csv`, 보통 수백 KB 이하)만 사용하도록 설계되어 있다.** 전체 스냅샷이 꼭 필요한 예외 상황(§3.0.1 하단)에서도 web 환경에서는 실패를 가정하고 월별 파일 누적 로드로 우회하라.

### 카테고리·체인 표준 디렉터리 레이아웃

본 저장소는 **2단계 분류**를 사용한다: `{category}/{chain}/`. 카테고리 예: `convenience` (편의점), `grocery` (마트), `cafe`, `pharmacy`, `restaurant`. 체인 예: `emart24`, `gs25`, `starbucks`.

각 체인 디렉터리는 다음 파일들로 구성된다.

| 경로 | 내용 | 권장 사용 |
|---|---|---|
| `{category}/{chain}/{YYYY}/{MM}.csv` | 신규 등록 월별 분배 — 각 매장은 본인의 월에 1회만 등장 | **기본** — 거의 모든 질의에서 사용 |
| `{category}/{chain}/README.md` | **그 체인 고유의 컬럼 정의·서비스 플래그 의미** (반드시 먼저 읽을 것) | 분석 전 1회 로드 |
| `{category}/{chain}/CHANGELOG.md` | 주간 변경 다이제스트 (사람이 읽기용) | 참고용 |
| `{category}/{chain}/_summary.json` | 자동 생성 요약 (총 매장 수, 시도별 카운트, 연도별 등록 추세, 월별 파일 목록) | 통계·전체 카운트 질의 |
| `{category}/{chain}/_index.csv` | 자동 생성 경량 인덱스 (code, title, sido, sigungu, lat, lng, first/last_seen_at) | 매장명·코드 검색 |
| `{category}/{chain}/_closure_candidates.csv` | 자동 생성 폐점 후보 (last_seen_at 갱신 중단 14일+ 매장만) | 폐점 추적 |
| `{category}/{chain}/_latest.csv` | 전체 매장 평면 스냅샷 (체인당 수 MB) | **예외 전용** — 위 보조 파일로 답할 수 없을 때만 |

> 보조 파일 3종(`_summary.json`, `_index.csv`, `_closure_candidates.csv`)은 매주 fetch 직후 `scripts/build_summary.py` 가 자동 생성한다. 모두 web_fetch 사이즈 제약 안에 들어오도록 설계되어 있어 Claude.ai web 환경에서도 안전하게 받을 수 있다.

체인별 컬럼·플래그가 일부 다를 수 있다. 분석 전에 해당 체인의 `{category}/{chain}/README.md` 를 먼저 로드하라.

예: emart24 (convenience 카테고리) 의 2025년 12월 파일은
`https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/convenience/emart24/2025/12.csv`

현재 수록 체인:
- `convenience/emart24/` — 약 5,700 매장, 매주 월 03:00 KST 갱신, `open_date` 기반 월별 파티션
- `convenience/gs25/` — 약 17,800 매장, 매주 월 04:00 KST 갱신, `first_seen_at` 기반 월별 파티션 (§2 마지막 항목 참조)

## 2. 모든 체인에 공통으로 적용되는 로드 규칙

다음 규칙은 본 저장소의 모든 체인 CSV 에 공통으로 적용된다. 체인 고유 컬럼은 별도로 `{chain}/README.md` 를 확인하라.

- `code` 컬럼은 **항상 문자열로 읽는다**. zero-pad 정수형 식별자(emart24: `"00060"`)이거나 영숫자(GS25: `"VQ670"`)이며, 정수 변환 시 데이터가 손상된다.
- `lat` / `lng` 는 float (도 단위, WGS84). 한반도 범위는 대략 33-39°N, 124-132°E.
- `open_date` / `end_date` / `start_hhmm` / `end_hhmm` / `is_24h` / `phone` / `address_detail` / `tobacco_license` 등은 **체인에 따라 존재하지 않을 수 있다**. 컬럼 부재 자체가 데이터 결함이 아니다 — 해당 체인 API의 제공 범위 차이일 뿐. 분석 전 `{chain}/README.md` 의 컬럼 목록을 확인하라.
- `svc_*` 로 시작하는 컬럼은 `0/1` 서비스 플래그다. 종류·개수는 체인마다 다르므로 `{chain}/README.md` 참조.
- 일부 체인은 `services` 컬럼(`;` 구분 raw 토큰)을 추가로 제공한다. **`services` 가 있으면 그것을 우선 신뢰하라** — `svc_*` 0/1 매핑이 일부 alias 누락으로 부정확할 수 있다 (예: GS25의 `gopizza`/`self_cook`/`tax` 응답 alias).
- `first_seen_at` 은 본 레포가 처음 관측한 일자, `last_seen_at` 은 가장 최근 관측 일자다 — 폐점 추정에 활용 가능.
- `current_month_file` (`_latest.csv` 에만 존재) 은 해당 매장이 위치한 월별 CSV 의 상대 경로 prefix (예: `"2015/03"`).
- **월별 파티션 키는 체인마다 다르다**: emart24 = `open_date.year/month` (실제 매장 오픈일), GS25 = `first_seen_at.year/month` (본 레포 최초 관측일, GS25 API가 오픈일을 제공하지 않기 때문). GS25의 부트스트랩 시점(2026-04-30)에는 모든 매장이 단일 월 파일(`2026/04.csv`)에 집중되어 있으며, 이는 데이터 결함이 아니라 정의된 동작이다.

## 3. 활용 패턴

### 3.0 본 데이터셋의 일차 용도 [필독]

**이 데이터셋은 "월별로 새로 추가된 매장 현황 확인"이 거의 모든 사용 케이스다.** 사용자 질문은 대개 다음 형태다:

- "이번 달 새로 오픈한 매장 알려줘"
- "최근 1달 / 지난 분기 신규 매장 추세는?"
- "2025년 12월에 오픈한 강남구 매장은?"

→ **이런 질의는 모두 월별 파일(`{category}/{chain}/{YYYY}/{MM}.csv`) 만으로 답할 수 있다.** `_latest.csv` 는 로드하지 마라.

### 3.0.1 체인 미명시 시 기본 동작

사용자 질문에 편의점 체인이 명시되지 않은 경우, **기본값으로 emart24 (`convenience/emart24/`) 를 사용한다.** 이는 본 데이터셋의 첫 수록 체인이며 가장 오랜 시계열을 가진다. GS25 등 다른 체인은 사용자가 명시적으로 지정한 경우에만 사용한다.

### 3.0.2 파일 선택 — 월별 파일이 default

**기본 규칙**: 항상 월별 파일(`{YYYY}/{MM}.csv`)부터 시도하라. 한 파일당 50~300행으로 토큰 효율이 높고, web_fetch 사이즈 제약도 회피한다.

| 질문 유형 | 권장 파일 |
|---|---|
| "이번 달 / 최근 1달 신규 오픈" | 현재 월·전월 파일 2개 (`{YYYY}/{MM}.csv`) |
| "지난 분기 / 최근 N개월 신규" | 해당 N개 월별 파일 |
| "특정 연도 오픈 추세" | 그 연도의 12개 월별 파일 |
| "특정 월의 신규 매장" | 그 월의 단일 파일 |

**예외 케이스 — 월별 파일로 답할 수 없는 드문 상황** (실제 발생 빈도 매우 낮음):

다음 케이스는 월별 파일만으로 답할 수 없다. **먼저 보조 파일을 시도하고, 그래도 부족할 때만 `_latest.csv` 를 마지막 수단으로 고려한다.**

| 질문 유형 | 1순위 (web 안전) | 2순위 (fallback) |
|---|---|---|
| "체인 전체 매장 수·통계" | `_summary.json` | — |
| "시도/구별 매장 분포" | `_summary.json` (`by_sido`) | — |
| "특정 매장명·코드 검색" | `_index.csv` | `_latest.csv` |
| "폐점 후보 (last_seen_at 갱신 중단)" | `_closure_candidates.csv` | — |
| "현재 영업 중 매장 전수 위치/속성/플래그 분석" | 모든 월별 파일 누적 로드 | `_latest.csv` (web 환경에서는 사이즈로 실패 가능) |

**규칙**:
- 보조 파일(`_summary.json`, `_index.csv`, `_closure_candidates.csv`)은 web_fetch 사이즈 안에 들어오도록 설계되었다 — 항상 우선 시도
- `_latest.csv` 는 마지막 수단. Claude.ai web 환경에서는 사이즈 초과로 실패할 수 있고, 실패 시 사용자에게 "전체 스냅샷은 web 환경에서 받지 못함" 을 알리고 월별 파일 누적으로 우회 또는 Claude Code(로컬 CLI) 사용을 안내

**체인별 함정**:
- **emart24**: 월별 파티션이 실제 매장 `open_date` 기반이므로 "최근 1달 오픈" 질문에 정확하다.
- **GS25**: 월별 파티션이 `first_seen_at` 기반(본 레포 최초 관측일)이다. 부트스트랩 시점(2026-04-30)에는 17,800개 매장 전부가 `convenience/gs25/2026/04.csv` 한 파일에 집중되어 있다. **GS25에서 "최근 1달 신규 오픈"은 부트스트랩 직후엔 의미가 없다** — 향후 매주 자동 실행으로 새 월 파일이 누적되면서 점차 의미를 가진다. 사용자에게 이 한계를 짧게 알리고 가능한 범위 내에서 답하라.

### 3.1 자연어 분석 요청 예시 (월별 파일 기반)

체인 미명시 시 §3.0.1에 따라 emart24 기본값 사용. 거의 모든 질의는 월별 파일 1~수 개만으로 답할 수 있다.

- "이번 달 새로 오픈한 매장 알려줘" → 현재 월 파일 1개
- "최근 1달 신규 오픈 추세" → 현재 월·전월 2개
- "지난 분기(3개월) 신규 오픈 추세를 월별 막대그래프로" → 3개 파일
- "2025년 12월에 강남구에 오픈한 매장은?" → 단일 월 파일
- "특정 좌표 1km 반경 안 최근 6개월 신규 오픈" → 6개 월 파일

### 3.2 변경 이력 기반 시계열 질의

월별 신규 매장 추세는 월별 파일을 직접 비교하는 것이 가장 단순하다. 시계열 변경 추적을 위한 git 사용은 로컬 환경(Claude Code)에서만 권장한다.

- "최근 N개월 월별 파일을 비교해서 신규 매장 추세를 그려줘" (web/local 모두 가능)
- "특정 매장 코드의 서비스 플래그 변경 이력 추적" (예외 케이스 §3.0.2 참조 — 로컬 환경에서 git log 권장)

### 3.3 RAG / 벡터 인덱싱 (예외 케이스)

자연어 매장 검색(예: "공항 근처 24시간 와인 파는 곳")은 §3.0.2 의 예외 케이스 1번에 해당하며 전수 데이터가 필요하다. **로컬 환경에서 월별 파일들을 모두 합쳐 임베딩하라** — `_latest.csv` 를 단일 파일로 받는 대신 `{chain}/{YYYY}/*.csv` 를 누적해서 동일 결과를 얻는다 (web_fetch 사이즈 제약 회피).

### 3.4 좌표 기반 분석

`lat` / `lng` 가 float 으로 제공되므로 별도 지오코딩 없이 반경 검색·클러스터링·heatmap 이 가능하다. 본 레포는 GIS 가공물을 제공하지 않으니 사용자가 직접 처리한다.

## 4. 데이터 한계 — AI 가 미리 알아야 할 사실

### 4.1 비현실 미래 날짜는 원천 API의 알려진 noise — 데이터 손상이 아니다 [중요]

원천 API 응답에 다음과 같은 비현실 날짜 행이 포함될 수 있다. **본 레포는 원천 응답을 충실히 보존하므로 이런 행이 그대로 남는다 — 본 레포의 손상이 아니다.**

- `open_date = 9999-12-31` — 미정/sentinel 값 (오픈일 미확정 매장)
- `open_date = 2100-12-XX` — 비현실 미래 (입력 오류 추정)
- 결과적으로 `convenience/emart24/9999/12.csv`, `convenience/emart24/2100/12.csv` 같은 디렉터리가 생성된다

**AI는 이러한 행을 "데이터 손상"으로 보지 말고, 단순히 "원천 API의 알려진 noise"로 인식하고 무시·필터링하라.** 이 행 때문에 다른 정상 데이터에 대한 추론을 흔들지 않도록 한다.

권장 필터:
```python
df = df[df['open_date'].between('2007-01-01', '2030-12-31')]
```
또는 `open_date` 컬럼이 없는 체인(예: GS25)이라면 `first_seen_at` 기준으로 동일하게 필터.

### 4.2 기타 한계

- 매장 폐점은 별도 컬럼이 아니라 `last_seen_at` 갱신 중단으로만 추정 가능하다 (정밀 추적은 후속 SPEC).
- `open_date` 가 미래 시점인 정상 예정 오픈 매장(예: 다음 달 오픈 예정)도 포함될 수 있다 — §4.1 의 비현실 sentinel 과 구분하라. 실제로 오픈하지 않을 수도 있다.
- GS25 응답은 `lat` 필드가 경도, `longs` 필드가 위도로 **이름이 반전**되어 있다. 본 레포는 정규화 시 swap을 적용해 CSV에는 표준 의미(`lat`=위도, `lng`=경도)로 저장하므로 직접 사용해도 된다.
- 원천 API 구조 변경 시 해당 체인의 수집이 일시 중단될 수 있다 (마지막 성공 실행은 README 배지로 확인).
- 옛 경로(`emart24/...` 최상위) 는 2026-04-30 시점의 정적 스냅샷으로 보존되며 더 이상 갱신되지 않는다. 최신 데이터는 항상 `convenience/{chain}/...` 를 사용하라.

## 5. 라이선스 / 출처 표기

분석 결과를 외부 공유할 때 다음을 포함하라:

> Source: itda-skills/data-retail (CC-BY-NC-4.0). Original copyright belongs to each convenience store chain.

## 6. 문의

본 데이터셋과 자동화 파이프라인은 **[스킬.잇다 (itda.work)](https://itda.work)** 에서 운영한다. 스킬·Claude 자동화 개발/교육 문의는 `dev@itda.work`.
