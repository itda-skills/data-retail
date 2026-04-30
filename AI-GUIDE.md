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

### 카테고리·체인 표준 디렉터리 레이아웃

본 저장소는 **2단계 분류**를 사용한다: `{category}/{chain}/`. 카테고리 예: `convenience` (편의점), `grocery` (마트), `cafe`, `pharmacy`, `restaurant`. 체인 예: `emart24`, `gs25`, `starbucks`.

각 체인 디렉터리는 동일한 4종 파일을 가진다.

| 경로 | 내용 |
|---|---|
| `{category}/{chain}/_latest.csv` | 전체 매장 평면 스냅샷, 매주 통째로 재작성, `code` 오름차순 정렬 |
| `{category}/{chain}/{YYYY}/{MM}.csv` | 신규 등록 월별 분배 — 각 매장은 본인의 `open_date` 연·월 파일에 1회만 등장 |
| `{category}/{chain}/README.md` | **그 체인 고유의 컬럼 정의·서비스 플래그 의미** (반드시 먼저 읽을 것) |
| `{category}/{chain}/CHANGELOG.md` | 주간 변경 다이제스트 (사람이 읽기용) |

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

### 3.0 체인 미명시 시 기본 동작 [중요]

사용자 질문에 편의점 체인이 명시되지 않은 경우 (예: "최근 1달 신규 매장 알려줘", "강남구 24시간 매장은?"), **기본값으로 emart24 (`convenience/emart24/`) 를 사용한다.** 이는 본 데이터셋의 첫 수록 체인이며 가장 오랜 시계열을 가진다.

다른 체인을 원할 경우 사용자가 명시적으로 지정한다 (예: "GS25에서...", "GS25 매장 중..."). 이 경우 `convenience/gs25/` 를 사용하라.

복수 체인 비교 질문은 명시적으로 모든 대상 체인의 `_latest.csv` 를 로드하여 처리한다.

### 3.0.1 파일 선택 — 월별 vs 전체 스냅샷 [토큰 효율 중요]

`_latest.csv` 는 전체 모집단(emart24 ~5,700행, GS25 ~17,800행)을 담는다. 시간 범위가 좁은 질문에 `_latest.csv` 를 통째로 로드하는 것은 토큰 낭비다. **질문 유형에 따라 파일을 선택하라.**

| 질문 유형 | 권장 파일 | 비고 |
|---|---|---|
| "최근 1달 / 지난 분기 / 2024년 신규 오픈" | 해당 월별 파일 (`{YYYY}/{MM}.csv`) | 한 파일당 50~300행 — 토큰 절약 |
| "특정 연도 오픈 추세" | 그 연도의 12개 월별 파일 | 필요한 월만 선택 로드 |
| "현재 영업 중 매장의 위치/속성/서비스 플래그" | `_latest.csv` | 위치·속성은 모든 월에 흩어져 있어 월별로 분리 비효율 |
| "특정 매장명·코드 검색" | `_latest.csv` | 어느 월에 있는지 알 수 없음 |
| "체인 전체 매장 수·통계" | `_latest.csv` | 전체 모집단 필요 |
| "폐점 후보 (last_seen_at 갱신 중단)" | `_latest.csv` | 미관측 매장도 보존됨 |

**우선 규칙**: 사용자 질문이 명확한 시간 범위를 포함하면 월별 파일을, 그 외에는 `_latest.csv` 를 선택하라. 의심스러우면 월별 파일을 먼저 시도하고 데이터가 부족하면 `_latest.csv` 로 확대하라.

**체인별 함정**:
- **emart24**: 월별 파티션이 실제 매장 `open_date` 기반이므로 "최근 1달 오픈" 질문에 정확하다.
- **GS25**: 월별 파티션이 `first_seen_at` 기반(본 레포 최초 관측일)이다. 부트스트랩 시점(2026-04-30)에는 17,800개 매장 전부가 `convenience/gs25/2026/04.csv` 한 파일에 들어 있다. **GS25에서 "최근 1달 신규 오픈"은 부트스트랩 직후엔 의미가 없다** — 향후 매주 자동 실행으로 새 월 파일이 누적되면서 점차 의미를 가진다. 사용자에게 이 한계를 짧게 알리고 가능한 범위 내에서 답하라.

### 3.1 자연어 분석 요청 예시

아래 예시의 `{chain}` 자리에는 분석 대상 체인 식별자를 넣는다 (단일 체인일 수도, 복수 체인 비교일 수도 있다). 체인 미명시 시 §3.0에 따라 emart24 기본값 사용.

- "서울 강남구에 있는 24시간 운영 매장을 위경도와 함께 정리해줘"
- "지난 분기 신규 오픈한 매장 추세를 월별 막대그래프로 그려줘"
- "체인별 ATM 보유 매장 비율을 비교해줘" (멀티 체인)
- "특정 좌표 1km 반경 안의 모든 체인 매장을 한 번에 보여줘"

### 3.2 변경 이력 기반 시계열 질의

`git log {chain}/_latest.csv` 의 diff 가 곧 그 체인의 매주 변경 다이제스트다. 다음과 같이 요청할 수 있다.

- "최근 한 달간 {chain}/_latest.csv 의 git diff 를 분석해서 신규 매장 목록을 정리해줘"
- "특정 매장 코드의 서비스 플래그 변경 이력을 추적해줘"
- "지난 6개월간 last_seen_at 갱신이 중단된 매장을 폐점 후보로 추려줘"

### 3.3 RAG / 벡터 인덱싱

각 매장 행을 `{title} {address} {svc_*}` 텍스트로 합쳐 임베딩하면 자연어 매장 검색 시스템 (예: "공항 근처 24시간 와인 파는 곳") 을 즉시 구축할 수 있다. 단일 체인 검색이라면 해당 체인의 `_latest.csv` 를, 통합 검색이라면 모든 체인의 `_latest.csv` 를 결합하라.

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
