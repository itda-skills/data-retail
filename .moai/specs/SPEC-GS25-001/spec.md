---
id: SPEC-GS25-001
title: GS25 매장 정보 주간 자동 수집 — GitHub Actions + 월별 CSV 누적 + latest snapshot
status: approved
priority: medium
version: 1.1.0
created_at: 2026-04-29
updated_at: 2026-04-30
history:
  - 2026-04-30 v1.1.0: Plan Phase 미해결 6개 항목 사용자 확정 — UA 정책(Chrome UA만, 레포 URL 비공개), 정규식 HTML 파싱(BS4 미사용, 실패 시 fail-fast), `update_changelog_gs25.py` 사본 격리(공유 리팩터링은 SPEC-COMMON-LIB-001로 미룸), 동 1건 실패 시 전체 워크플로우 실패(부분 수집 정책 폐기), VQ670 정적 fixture 고정. cron 시간(04:00 KST)은 유지.
  - 2026-04-29 v1.0.0: 초기 SPEC. 4단계 발견 파이프라인(부트스트랩 → 시도 → 군구 → 동 → 매장) 검증 완료. CSRFToken·이중 JSON 인코딩·lat/longs 필드 의미 반전 등 GS25 API 특이사항 수집기 정책으로 고정. emart24와 달리 OPEN_DATE 부재로 인한 월별 파티션 키를 `first_seen_at`으로 명시
related:
  - data-retail (this repo)
  - SPEC-EMART24-001 (선행 체인, 동일 sub-category `convenience/`)
depends_on: []
references:
  - https://gs25.gsretail.com/gscvs/ko/store-services/locations (CSRFToken 부트스트랩 페이지)
  - https://gs25.gsretail.com/gscvs/ko/gsapi/gis/searchGungu (군구 발견)
  - https://gs25.gsretail.com/gscvs/ko/gsapi/gis/searchDong (동 발견)
  - https://gs25.gsretail.com/gscvs/ko/store-services/locationList (매장 검색, 이중 JSON 인코딩)
  - https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
---

# SPEC-GS25-001 — GS25 매장 정보 주간 자동 수집

## 배경

`data-retail/` 레포는 국내 주요 편의점 체인의 매장 데이터를 GitHub Actions로 주 1회 자동 수집·공개하는 오픈 데이터 저장소다. 본 SPEC은 두 번째 체인인 **GS25**의 수집 파이프라인을 정의하며, SPEC-EMART24-001의 디렉터리·CSV·트랜잭션·테스트 규약을 그대로 계승한다.

GS25는 emart24와 달리 **단일 평면 API가 아닌 4단계 발견 파이프라인**을 강제한다. `https://gs25.gsretail.com` 의 매장 검색 페이지를 부트스트랩으로 열어 **세션별 CSRFToken**과 쿠키 jar를 받은 뒤, 17개 시도(MOIS 행정코드)를 정적 파싱하고, 시도→군구→동을 순차 발견(`searchGungu`, `searchDong`)한 다음, 마지막으로 동 단위 `locationList` POST를 호출해 매장을 받는다. 응답은 **이중 JSON 인코딩**으로 감싸여 있어 `json.loads(json.loads(raw))`로 풀어야 하며, 매장 좌표 필드는 **`lat`/`longs` 라는 이름이 실제 값과 의미가 반전(lat=경도, longs=위도)** 되어 있다.

또한 GS25 API는 `open_date`, `end_date`, 영업시간, 전화번호, `address_detail`, 담배소매인 면허 같은 emart24의 핵심 시계열 필드를 일체 제공하지 않는다. 대신 22여 종의 점포 부가 서비스 플래그(`offeringService` 배열)를 노출한다. 본 SPEC은 이러한 데이터 모델 차이를 의식적으로 수용하여 월별 파티션 키를 emart24의 `OPEN_DATE`가 아닌 **본 레포가 처음 관측한 일자(`first_seen_at`)** 로 변경한다. 이는 SPEC-EMART24-001과의 의도적 의미 차이이며, 두 체인 데이터를 합쳐 사용할 외부 사용자에게 명시적으로 알려야 한다.

상용 지도 서비스와 차별화되는 가치는 SPEC-EMART24-001과 동일하다. 지점 검색이 아니라 **매장 시계열 데이터(언제 처음 관측, 언제 미관측 시작, 서비스 변동)** 의 공개·재현 가능한 아카이브다.

## 목표

- GS25 매장 데이터를 주 1회 자동 수집하여 월별 CSV 파일로 누적 저장
- SPEC-EMART24-001과 동일한 디렉터리 패턴(`convenience/{chain}/`)을 사용하여 신규 체인 추가 시 일관된 구조 유지
- GS25 API의 4단계 발견 파이프라인(부트스트랩 → 시도 → 군구 → 동 → 매장)을 워크플로우 1회 실행 안에 완결
- 세션 토큰·이중 JSON·좌표 반전 등 GS25 고유 API 특이사항을 단위 테스트로 고정하여 회귀 즉시 감지
- GitHub Actions 무료 한도 내에서 운영 (public repo 무제한). 1회 실행 약 30분 예상

## 비목표

- 실시간/일간 갱신 (주 1회로 충분)
- 폐점 자동 추적 (후속 SPEC-CLOSURE-DETECT-001)
- 알림 발송 (후속 SPEC-NOTIFY-001)
- 데이터 API 서버 (raw CSV 직접 접근으로 충분)
- emart24와 GS25 간 동일 매장 cross-validation
- GS25 본사 외 GS Fresh, GS Supermarket 등 자매 브랜드 수집
- 사용자별 인증·과금 (public repo 무료 운영)

## 데이터 소스

본 SPEC의 모든 엔드포인트는 2026-04-29 본 레포 메인 세션에서 직접 검증되었다. 향후 응답 구조가 변경되면 REQ-GS25-011 단위 테스트가 즉시 실패하도록 fixture를 고정한다.

### 4단계 발견 파이프라인

| Step | 메서드·경로 | 목적 | 응답 형식 | 비고 |
|---|---|---|---|---|
| 0 | `GET /gscvs/ko/store-services/locations` | 세션 부트스트랩 — CSRFToken + 쿠키 jar 획득, 17개 시도 정적 파싱 | HTML, 인라인 스크립트 `ACC.config.CSRFToken = "<UUID-v4>"` | 매 워크플로우 실행 시작 시 1회 호출. 토큰은 세션·쿠키와 바인딩되어 재현 불가. 17 시도 코드는 `<option value="...">` 정적 파싱 |
| 1 | (없음, Step 0의 HTML에서 추출) | 시도(sido) 코드 17개 추출 | 인라인 `<option>` 태그 | MOIS 행정코드: 11 서울, 26 부산, 27 대구, 28 인천, 29 광주, 30 대전, 31 울산, 36 세종, 41 경기, 43 충북, 44 충남, 46 전남, 47 경북, 48 경남, 50 제주, 51 강원, 52 전북. 하드코딩 금지 — 향후 명칭 변경(예: 강원→강원특별자치도) 자동 반영 |
| 2 | `GET /gscvs/ko/gsapi/gis/searchGungu?stb1={sido_code}` | 시도별 군구 목록 발견 | JSON `{"result": [["1168","강남구"], ...], "resultCode": "00000"}` (단일 인코딩) | 동일 세션(쿠키·Referer 필요). 약 250개 군구 |
| 3 | `GET /gscvs/ko/gsapi/gis/searchDong?stb1={sido}&stb2={gungu}` | 군구별 동 목록 발견 | JSON `{"result": [["11680103","개포동"], ...]}` (단일 인코딩) | 동 코드는 8자리 행정코드 |
| 4 | `POST /gscvs/ko/store-services/locationList?CSRFToken={token}` | 동별 매장 목록 검색 | HTTP 200, `Content-Type: application/json`, **이중 JSON 인코딩** — `json.loads(json.loads(raw))` 후 `{"results": [...]}` | 동 1개당 1회 호출. 응답이 빈 배열이어도 정상(매장 없는 동) |

### Step 0 — 부트스트랩 세부

- 헤더: `User-Agent: Mozilla/5.0 ...Chrome/130.0`
- 쿠키 jar 영속 — 모든 후속 호출에 동일 jar 사용
- 토큰 추출 정규식: `ACC\.config\.CSRFToken\s*=\s*"([^"]+)"`
- 토큰은 세션과 1:1 — 다른 세션에서 재현 불가, 페이지 로드마다 새로 발급

### Step 4 — 매장 검색 요청 본문

`Content-Type: application/x-www-form-urlencoded; charset=UTF-8`, `X-Requested-With: XMLHttpRequest`, `Referer: https://gs25.gsretail.com/gscvs/ko/store-services/locations`

폼 필드 (모든 `searchType*=0`로 고정 — 서비스로 필터링하지 않음):

```
pageNum=1&pageSize=50000&searchShopName=
&searchSido={sido}&searchGugun={gungu}&searchDong={dong}
&searchType=&searchTypeService=0
&searchTypeFreshGanghw=0&searchTypeMusinsa=0&searchTypePosa=0
&searchTypeWine25=0&searchTypeGoPizza=0&searchTypeSpiritWine=0
&searchTypeCardiacDefi=0&searchTypeFishShapedBun=0&searchTypeSmartAtm=0
&searchTypeSelfCookingUtensils=0&searchTypeDeliveryService=0&searchTypeParcelService=0
&searchTypePotatoes=0&searchTypeTaxrefund=0&searchTypeWithdrawal=0
&searchTypeATM=0&searchTypePost=0&searchTypeSelf25=0
&searchTypeDrug=0&searchTypeInstant=0&searchTypeCafe25=0&searchTypeToto=0
```

### 매장 레코드 필드 (Step 4 응답 `results[]`)

- `shopCode` (string, 예: `"VQ670"`) — 고유 식별자
- `shopName` (string)
- `address` (string, 도로명 + 지번 혼재 단일 라인)
- **`lat` (string) — 실제는 경도** (예: `"127.045318254341"`)
- **`longs` (string) — 실제는 위도** (예: `"37.4792069328551"`)
- `offeringService` (array of string) — 점포 부가 서비스 코드 배열. 관측된 값:
  `cafe25, instant, drug, post, withdrawal, atm, taxrefund, smart_atm, self_cooking_utensils, delivery_service, parcel_service, potatoes, cardiac_defi, fish_shaped_bun, wine25, go_pizza, spirit_wine, fresh_ganghw, musinsa, posa, toto, self25`

### emart24 대비 부재 필드

GS25 API는 다음 필드를 **제공하지 않는다**:

- `open_date` (오픈일)
- `end_date` (폐점일)
- 영업시간 (`start_hhmm`, `end_hhmm`, `is_24h`)
- `phone` (전화번호)
- `address_detail` (상세 주소)
- `tobacco_license` (담배소매인 면허)

이 부재는 다음 두 가지 결정으로 이어진다:

1. **월별 파티션 키 변경**: emart24가 사용한 `OPEN_DATE`를 사용할 수 없으므로, 본 SPEC은 **`first_seen_at`(본 레포가 매장을 처음 관측한 일자)의 연·월**을 파티션 키로 사용한다. 이는 SPEC-EMART24-001과 의도적으로 의미가 다른 설계 선택이며, README에 명시한다.
2. **CSV 컬럼 축소**: 위 6개 필드를 GS25 CSV에서 제거한다.

### 데이터량 추정

- 17 시도 × 평균 ~15 군구/시도 ≈ 약 250 군구
- 250 군구 × 평균 ~14 동/군구 ≈ 약 3,500 동
- 1회 풀 실행 = Step 0 ×1 + Step 2 ×17 + Step 3 ×250 + Step 4 ×3,500 ≈ **약 3,768 HTTP 호출**
- 매너 throttle 0.5초 적용 시 약 31분 — `weekly-emart24.yml`(약 2분)과 시간대를 분리한다

## 데이터 구조

### 디렉터리 레이아웃

SPEC-EMART24-001과 동일한 sub-category 패턴을 따른다.

```
data-retail/                              (레포 루트)
├── README.md
├── LICENSE                               # CC-BY-NC-4.0 (데이터)
├── .github/
│   └── workflows/
│       ├── weekly-emart24.yml            # 기존
│       └── weekly-gs25.yml               # 신규: cron 매주 월요일 04:00 KST (emart24와 시간대 분리)
├── scripts/
│   ├── fetch_emart24.py                  # 기존
│   ├── fetch_gs25.py                     # 신규
│   ├── update_changelog.py               # 기존 (emart24 전용, 본 SPEC에서 미수정)
│   ├── update_changelog_gs25.py          # 신규: update_changelog.py의 사본, GS25 경로·카운트 규칙만 수정 (공유 리팩터링은 SPEC-COMMON-LIB-001)
│   ├── requirements.txt                  # requests
│   └── tests/
│       ├── test_fetch_emart24.py
│       └── test_fetch_gs25.py            # 신규
└── convenience/                          # sub-category: 편의점
    ├── emart24/                          # 기존 체인
    │   └── ...
    └── gs25/                             # 신규 체인
        ├── README.md                     # CSV 컬럼 정의, 서비스 플래그 의미, emart24와 다른 파티션 키 명시
        ├── CHANGELOG.md                  # 주간 변경 다이제스트
        ├── _latest.csv                   # 전체 매장 평면 스냅샷
        ├── 2026/
        │   ├── 04.csv                    # 첫 부트스트랩 실행 → 전 매장 여기로
        │   └── 05.csv                    # 이후 신규 관측 매장
        └── ...
```

### 월별 CSV 규칙 (REQ-GS25-005 참조)

- 파일명: `convenience/gs25/{YYYY}/{MM}.csv` (월 2자리 zero-padded)
- 한 매장은 **본인의 "신규 등록 월" 파일에 1회만 등장**
- "신규 등록 월" = **항상 매장의 `first_seen_at` 연·월** (본 레포가 매장을 처음 관측한 일자)
- emart24와의 차이: emart24는 `OPEN_DATE` 기준, GS25는 `first_seen_at` 기준. README에서 명시적으로 안내
- 부트스트랩(첫 실행) 시 모든 매장의 `first_seen_at`은 워크플로우 실행일 → 전 매장이 단일 월 파일(예: `2026/04.csv`)에 집중. 향후 주 단위 신규 매장만 추후 월 파일로 분산

### CSV 컬럼 정의

본 표는 **월별 CSV**의 컬럼 정의 (총 30개 컬럼)이다. `_latest.csv`는 본 표 30개 + `current_month_file` 1개 = 총 31개 컬럼 (Latest Snapshot 규칙 참조).

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `code` | string | API의 `shopCode` (예: `VQ670`) — 고유 식별자, 따옴표 보존 |
| `title` | string | API의 `shopName` |
| `address` | string | API의 `address` 그대로 (도로명·지번 혼재 단일 라인) |
| `lat` | float | **실제 위도** — API의 `longs` 필드를 swap 하여 저장 |
| `lng` | float | **실제 경도** — API의 `lat` 필드를 swap 하여 저장 |
| `services` | string | `offeringService` 배열을 알파벳순 정렬·세미콜론 join (예: `"atm;cafe25;wine25"`). 미관측 신규 서비스 코드 보존용 long string |
| `svc_cafe25` | int | 0/1 |
| `svc_instant` | int | 0/1 |
| `svc_drug` | int | 0/1 |
| `svc_post` | int | 0/1 |
| `svc_withdrawal` | int | 0/1 |
| `svc_atm` | int | 0/1 |
| `svc_taxrefund` | int | 0/1 |
| `svc_smart_atm` | int | 0/1 |
| `svc_self_cooking_utensils` | int | 0/1 |
| `svc_delivery_service` | int | 0/1 |
| `svc_parcel_service` | int | 0/1 |
| `svc_potatoes` | int | 0/1 |
| `svc_cardiac_defi` | int | 0/1 |
| `svc_fish_shaped_bun` | int | 0/1 |
| `svc_wine25` | int | 0/1 |
| `svc_go_pizza` | int | 0/1 |
| `svc_spirit_wine` | int | 0/1 |
| `svc_fresh_ganghw` | int | 0/1 |
| `svc_musinsa` | int | 0/1 |
| `svc_posa` | int | 0/1 |
| `svc_toto` | int | 0/1 |
| `svc_self25` | int | 0/1 |
| `first_seen_at` | string | ISO 날짜 — 본 레포가 처음 관측한 일자. 월별 파티션 키 |
| `last_seen_at` | string | ISO 날짜 — 가장 최근 워크플로우 실행 관측 일자 |

`svc_*` 화이트리스트는 본 SPEC으로 고정한다. 위 22종 외 신규 서비스 코드가 향후 API 응답에 등장하면:

- `services` 컬럼(long string)에는 정상 보존 (정보 소실 없음)
- `svc_*` 컬럼은 추가하지 않음 (스키마 안정성 우선)
- 워크플로우는 실패하지 않고 stderr 경고 로그를 남김 (`[WARN] unknown service code: <code>`) 및 GitHub Actions 요약에 기록
- SPEC 개정으로 신규 코드를 정식 컬럼화

### Latest Snapshot 규칙 (`convenience/gs25/_latest.csv`, REQ-GS25-005b 참조)

- 위치: `convenience/gs25/_latest.csv`
- 내용: 본 레포가 관측한 **전체 GS25 매장 평면 목록** (1회 부트스트랩 후 약 1.5만 행 추정)
- 매주 워크플로우 실행 시 **통째로 재작성** (append 아님, 정렬 키: `code` ASC)
- 컬럼: 월별 CSV와 동일 (위 표) + 다음 1개 추가
  - `current_month_file` (string): 해당 매장이 등록된 월별 CSV의 상대 경로 prefix (예: `"2026/04"`, `"2026/05"`)
- 포함 대상:
  - 이번 실행에서 관측된 모든 매장
  - **이번 실행에서 미관측이지만 이전에 관측된 매장도 유지** (last_seen_at은 직전 값 보존, 폐점 추적은 후속 SPEC)
- 용도:
  - 신규 매장 판정 소스 (REQ-GS25-004)
  - 변경 다이제스트 생성 소스 (REQ-GS25-006)
  - 외부 사용자의 "현재 전체 매장 1회 다운로드" 진입점

### 인코딩

UTF-8 (BOM 없음). LF 개행. RFC 4180 준수.

## 요구사항 (EARS)

### REQ-GS25-001 (Time-driven) — 주간 자동 실행

WHEN the GitHub Actions cron schedule fires every Monday at 04:00 KST, the system SHALL execute the full GS25 fetch pipeline.

**Acceptance criteria:**
- cron 표현식: `0 19 * * 0` (UTC 일요일 19:00 = KST 월요일 04:00)
- emart24(`0 18 * * 0`)와 1시간 시간대 분리하여 자원 경합·rate-limit 영향 회피
- 워크플로우 파일: `.github/workflows/weekly-gs25.yml`
- 수동 트리거 지원 (`workflow_dispatch`)
- 실행 환경: `ubuntu-latest`, Python 3.14+
- 실행 시간 45분 이내 정상 완료 (예상 31분 + 여유)

### REQ-GS25-002 (Ubiquitous) — 세션 부트스트랩

The system SHALL bootstrap a session by loading the GS25 store-locator HTML page once at the start of every workflow run, persisting cookies in a single `requests.Session` jar, and extracting the inline CSRFToken via regex.

**Acceptance criteria:**
- 엔드포인트: `GET https://gs25.gsretail.com/gscvs/ko/store-services/locations`
- User-Agent: 일반 Chrome UA 문자열만 사용 (예: `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36`)
- 본 저장소 URL이나 식별자는 UA에 포함하지 않음 (차단 회피 목적)
- `requests.Session` 1회 생성 후 모든 후속 호출에 재사용
- 토큰 추출 정규식: `ACC\.config\.CSRFToken\s*=\s*"([^"]+)"`
- 토큰 미발견 시 즉시 워크플로우 실패 (exit 1)
- HTML 파싱은 표준 라이브러리 `re` 정규식만 사용 (BeautifulSoup4 등 추가 의존성 도입 금지). 정규식 패턴:
  - CSRFToken: `ACC\.config\.CSRFToken\s*=\s*"([^"]+)"`
  - 시도 옵션: `<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>` (단, 시도 select 영역으로 한정해 추출)
- 위 두 패턴 중 하나라도 매치 0건이면 즉시 워크플로우 실패 (fail-fast). HTML 구조 변경을 즉시 감지하기 위함이며, GitHub Actions 기본 실패 이메일 알림으로 관리자에게 통지된다.
- 시도(sido) 17개 코드·이름은 동일 HTML의 `<option value="...">...</option>`을 위 정규식으로 파싱하여 추출. 하드코딩 금지
- 부트스트랩 호출 1회 후 0.5초 throttle 적용 후 다음 단계 진입
- 워크플로우 도중 401/403/500 응답이 발생하면 부트스트랩을 1회 재시도하고, 그래도 실패하면 즉시 실패 처리

### REQ-GS25-003 (Ubiquitous) — 군구·동 발견 파이프라인

The system SHALL discover all (sido, gungu, dong) tuples nationwide using the same session, with 0.5-second throttle between every HTTP call.

**Acceptance criteria:**
- 군구 발견: 시도 17개 각각에 대해 `GET /gscvs/ko/gsapi/gis/searchGungu?stb1={sido}` 호출. `Referer` 헤더 부트스트랩 페이지로 고정
- 동 발견: 군구 각각에 대해 `GET /gscvs/ko/gsapi/gis/searchDong?stb1={sido}&stb2={gungu}` 호출
- 응답 파싱: `json.loads(raw)`. `result` 배열 빈 값(rural 군구)도 정상으로 간주, 워크플로우 실패시키지 않음
- 응답에 `resultCode`가 존재하면 `"00000"`이 아닌 경우 즉시 실패 (실패 시 응답 본문을 GitHub Actions 요약에 기록)
- 모든 호출 간 0.5초 sleep
- 5xx/타임아웃 시 지수 백오프 재시도 3회 (1s → 2s → 4s)
- 4xx 즉시 실패

### REQ-GS25-004 (Event-driven) — 동 단위 매장 검색과 이중 JSON 디코딩

WHEN a (sido, gungu, dong) tuple is discovered, the system SHALL POST to `locationList` with the form-encoded body and decode the response with two consecutive `json.loads` calls.

**Acceptance criteria:**
- 엔드포인트: `POST https://gs25.gsretail.com/gscvs/ko/store-services/locationList?CSRFToken={token}`
- 헤더: `Content-Type: application/x-www-form-urlencoded; charset=UTF-8`, `X-Requested-With: XMLHttpRequest`, `Referer: https://gs25.gsretail.com/gscvs/ko/store-services/locations`
- 요청 본문: 본 SPEC "데이터 소스 → Step 4" 절의 폼 필드 전체. `searchType*=0`으로 모두 고정하여 서비스 필터링 없이 전 매장 수집
- 응답 디코딩: `data = json.loads(json.loads(raw_text))`. 첫 `json.loads`가 string을 반환하면 두 번째 `json.loads`로 dict 변환. dict에서 `results` 키 추출
- `results`가 빈 배열인 경우 정상 (해당 동에 GS25 매장 없음)
- 호출 간 0.5초 sleep
- 5xx/타임아웃 시 백오프 재시도 3회. 4xx는 즉시 실패. 401/403/500이 누적 5회 발생하면 부트스트랩(REQ-GS25-002)을 1회 재시도 후 계속

### REQ-GS25-005 (Event-driven) — 정규화와 좌표 swap

WHEN raw store records are received, the system SHALL normalize them to the CSV schema, swapping the API's mislabeled `lat` and `longs` fields to their true semantic meaning.

**Acceptance criteria:**
- 정규화 매핑:
  - `shopCode` → `code` (string 보존)
  - `shopName` → `title`
  - `address` → `address` (그대로)
  - **`longs` (string) → `lat` (float)** — 실제 위도
  - **`lat` (string) → `lng` (float)** — 실제 경도
  - `offeringService` → `services` (알파벳순 정렬·`;` join), `svc_*` 22개 0/1 컬럼
- 좌표 swap 로직 위에는 다음 주석을 반드시 포함:
  ```
  # GS25 API trap: lat/longs fields are inverted from their names.
  # API "lat" actually carries longitude, API "longs" actually carries latitude.
  ```
- `svc_*` 화이트리스트 외 코드는 `services` 컬럼에는 보존하되 `svc_*` 컬럼화하지 않고 stderr `[WARN] unknown service code: <code>` 로깅
- 같은 실행 내 중복 `code` 발견 시 워크플로우 실패 처리 (REQ-GS25-003 일관성)

### REQ-GS25-006 (Event-driven) — 신규 매장 판정과 월별 파티션

WHEN normalization completes, the system SHALL determine the "new month" file destination for each store using `_latest.csv` as the single source of truth, with `first_seen_at` as the partition key.

**Acceptance criteria:**
- 판정 소스: `convenience/gs25/_latest.csv` 1회 로드 → `code → row` 메모리 맵 (O(1) 룩업)
  - `_latest.csv` 부재(부트스트랩 첫 실행) 시: 빈 맵으로 시작, 모든 매장은 신규로 분류
  - 월별 CSV는 판정 소스로 사용하지 않음 (폴백·검증 시에만 스캔)
- 매장의 신규 등록 월 = **`first_seen_at.year/month`**
  - 신규 매장: `first_seen_at = today` (워크플로우 실행일) → 등록 월 결정
  - 기존 매장: 기존 row의 `first_seen_at` 보존 → 등록 월 변동 없음
- emart24와의 의도적 차이: emart24는 `OPEN_DATE` 기준이지만 GS25 API는 `OPEN_DATE`를 제공하지 않으므로 `first_seen_at`을 사용. 본 SPEC과 README에 명시
- `current_month_file`:
  - 신규: 새로 결정한 등록 월(예: `"2026/05"`)
  - 기존: `_latest.csv`의 기존 값 보존 (월 이동 없음, REQ-GS25-007)

### REQ-GS25-007 (Event-driven) — 월별 CSV 작성·갱신

WHEN store data is normalized, the system SHALL write each store to exactly one monthly CSV file based on its new-month destination, treating monthly CSV write and `_latest.csv` rewrite as a single transaction.

**Acceptance criteria:**
- 각 매장은 본인의 신규 등록 월 파일에 정확히 한 번만 존재
- 같은 매장이 이전 월 파일에서 발견되면 그 파일에서 행을 갱신 (월 이동 없음)
  - 갱신 대상 필드: `title`, `address`, `lat`/`lng`, `services`, 모든 `svc_*`, `last_seen_at`
  - 보존 필드: `code`, `first_seen_at`
- 새 매장은 신규 등록 월 파일에 append (파일이 없으면 디렉터리·파일 생성)
- API 응답에서 사라진 매장은 삭제하지 않음 (마지막 `last_seen_at` 유지) — 폐점 추적은 후속 SPEC
- CSV 컬럼 순서는 본 SPEC의 "CSV 컬럼 정의" 표 그대로 고정 (월별 CSV는 `current_month_file` 컬럼 미포함)
- 월별 CSV 갱신과 `_latest.csv` 재작성은 **동일 트랜잭션** — 둘 중 하나만 성공해서는 안 됨 (REQ-GS25-010 롤백 정책)

### REQ-GS25-005b (Event-driven) — Latest Snapshot 재작성

WHEN store data is normalized, the system SHALL rewrite `convenience/gs25/_latest.csv` from scratch with the current full store population.

**Acceptance criteria:**
- 위치: `convenience/gs25/_latest.csv`
- 매주 **통째로 재작성** (in-place 갱신 아님, 임시파일 → atomic rename)
- 정렬: `code` ASC (안정적 git diff 보장)
- 행 구성:
  - 이번 실행에서 API 관측된 모든 매장 (정규화된 최신 값, `last_seen_at = today`)
  - 이전에 관측되었으나 이번 실행에 미관측된 매장도 보존 (`last_seen_at`은 직전 값 유지)
- 컬럼: "CSV 컬럼 정의" 표 30개 + `current_month_file` 1개 = 31개
  - `current_month_file`: 해당 매장이 위치한 월별 CSV의 상대 경로 prefix
  - 신규 매장: REQ-GS25-006에서 결정된 신규 등록 월
  - 기존 매장: 직전 `_latest.csv`의 값 보존 (월 이동 금지)
- 부트스트랩(첫 실행): `_latest.csv`가 없으면 새로 생성. 모든 매장은 신규로 처리
- 무결성: 같은 실행 내 `code` 중복 시 워크플로우 실패 (REQ-GS25-005)

### REQ-GS25-008 (Event-driven) — 변경 다이제스트 작성

WHEN the monthly CSVs are updated, the system SHALL append a weekly digest entry to `convenience/gs25/CHANGELOG.md`.

**Acceptance criteria:**
- 형식 (역순 시간 정렬, 최신이 위):

```
## 2026-04-29 (주간 갱신)

- 신규 등록: 12개 (2026/04 +5, 2026/05 +7)
  - 신규 매장 일부: 강남역점, 광화문점, ...
- 정보 갱신: 38개 매장 (서비스 플래그 22, 주소 11, 좌표 5)
- API 미관측: 3개 매장 — 폐점/이전 가능성

실행: actions run #42
```

- 신규 매장 목록은 최대 10개까지 표시, 초과 시 "외 N개"
- 정보 갱신은 카운트만 (개별 diff는 git diff)
- 실행 링크는 GitHub Actions 환경변수 (`GITHUB_RUN_ID`, `GITHUB_REPOSITORY`)에서 추출
- 다이제스트 분석 소스: `git diff HEAD~1 -- convenience/gs25/_latest.csv` 단일 파일 분석
- 본 SPEC에서 사용하는 스크립트는 `scripts/update_changelog_gs25.py` — `scripts/update_changelog.py`를 그대로 복사한 **사본(sibling COPY)**이며, `--chain` 인자를 추가한 공유 스크립트가 아님. GS25 전용 경로(`convenience/gs25/`)와 카운트 규칙만 본 사본에서 수정한다.
- emart24 스크립트 `scripts/update_changelog.py`는 본 SPEC 범위에서 수정하지 않는다. 두 스크립트의 공통 로직 추출은 후속 SPEC-COMMON-LIB-001에서 처리한다.

### REQ-GS25-009 (Event-driven) — 자동 커밋

WHEN updates are written, the system SHALL commit and push changes via the workflow.

**Acceptance criteria:**
- 커밋 작성자: `github-actions[bot]`
- 커밋 메시지: `chore(gs25): weekly fetch {YYYY-MM-DD} — 신규 N, 갱신 M, 미관측 K`
- 변경 사항이 없으면 커밋하지 않음
- `[skip ci]` 플래그 포함하여 무한 루프 방지
- main 브랜치에 직접 push (PR 없이)

### REQ-GS25-010 (Ubiquitous) — 매너 throttle

The system SHALL be a polite client to the upstream API.

**Acceptance criteria:**
- 모든 HTTP 호출(Step 0/2/3/4) 사이에 기본 0.5초 sleep, `--delay` CLI 인자로 조정 가능
- 1회 풀 실행 ≈ 약 3,768 HTTP 호출 × 0.5초 ≈ 31분
- robots.txt 점검 결과는 첫 실행 전 README에 명시 (CLAUDE.local.md 운영 메모에 기록)
- User-Agent는 식별 가능한 매너 UA를 사용 (Windows Chrome 패턴 + 본 레포 URL을 포함하는 것을 검토)

### REQ-GS25-011 (Ubiquitous) — 워크플로우 실패 가시성과 트랜잭션 무결성

The system SHALL surface failures clearly without breaking the data, and SHALL guarantee atomic consistency between monthly CSVs and `_latest.csv`.

**Acceptance criteria:**
- 부트스트랩 토큰 추출 실패, 군구·동 발견 실패, 4xx 응답, 정규화 실패, 중복 code 발견 시 워크플로우 exit code 1
- 정규화 실패·중복 code 발견 시 즉시 실패하고 부분 작성된 파일 롤백 (commit 안 함)
- 롤백 범위: 영향받은 월별 CSV + `_latest.csv` 모두. 둘 중 하나만 갱신된 상태로 종료 금지
- `_latest.csv`는 임시파일(`_latest.csv.tmp`)에 먼저 작성한 뒤 atomic rename으로 교체. rename 실패 시 임시파일 삭제
- 동 단위 `locationList` POST가 3회 백오프 재시도 후에도 실패하면 즉시 워크플로우 전체를 실패 처리한다. 부분 수집은 허용하지 않는다 (데이터 일관성 우선).
- 워크플로우 실패는 GitHub Actions의 기본 실패 이메일 알림으로 저장소 소유자에게 통지된다 (별도 알림 채널 비도입). 본 SPEC 채택 후 `Settings → Notifications → Actions`에서 "Only notify for failed workflows that I personally triggered" 옵션이 OFF인지 1회 확인할 것을 README 운영 가이드에 명시한다.
- 마지막 성공 실행일을 README 배지로 표기

### REQ-GS25-012 (Ubiquitous) — 라이선스와 사용 안내

The system SHALL document data licensing and attribution clearly.

**Acceptance criteria:**
- 레포 루트 `LICENSE`(CC-BY-NC-4.0)와 `scripts/`(MIT)는 SPEC-EMART24-001과 공유
- `convenience/gs25/README.md`:
  - "본 데이터는 GS25 공식 점포찾기 페이지(`gs25.gsretail.com`)에서 자동 수집된 가공물이며, 원본 저작권은 (주)지에스리테일에 있습니다." 명시
  - 비상업적 사용 권장, 상업적 사용은 직접 문의
  - 갱신 주기, 컬럼 정의, 알려진 한계 (특히 OPEN_DATE 부재로 인한 `first_seen_at` 기반 파티션, emart24와의 의미 차이)
  - raw URL 사용 예시
  - 좌표 swap 보존 안내 (외부 도구가 본 CSV의 `lat`/`lng`을 표준 의미로 사용 가능)
- README의 "운영 가이드" 섹션에 GitHub Actions 실패 알림 설정 확인 절차를 1회 안내한다 (REQ-GS25-011 참조).

### REQ-GS25-013 (Ubiquitous) — 테스트

The system SHALL include unit tests for normalization, partition routing, and GS25-specific API quirks.

**Acceptance criteria:**
- 파일: `scripts/tests/test_fetch_gs25.py`
- mock HTTP fixture (실 API 호출 없음)
- 필수 테스트 항목:
  - **CSRFToken 추출 정규식** — 정상 HTML과 토큰 부재 HTML 모두 검증
  - **이중 JSON 인코딩 unwrap** — `locationList` 응답 형태 fixture로 고정. 단일 JSON으로 변경되면 즉시 실패하도록 schema assertion
  - **lat/longs swap 정확성** — 알려진 매장 fixture로 회귀 검증한다:
    - VQ670 (서울 강남구 개포로15길10) 매장 응답을 2026-04-29 검증 시점 그대로 `tests/fixtures/gs25_vq670.json`에 정적으로 저장한다.
    - 정규화 후 결과가 `lat ≈ 37.4792, lng ≈ 127.0453` 임을 단언한다 (소수 4자리 비교).
    - GS25가 해당 매장을 폐점·재할당하더라도 본 fixture는 갱신하지 않는다. 좌표 swap 로직 자체의 회귀를 막는 것이 목적이므로 실 데이터 동기화는 비목표.
  - **시도 17개 정적 파싱** — HTML fixture로 17개 옵션 추출, 향후 명칭 변경(예: 강원 → 강원특별자치도) 시 코드 무영향 회귀 검증
  - **시도 17개 정규식 파싱**: 검증 시점 페이지 HTML도 `tests/fixtures/gs25_locations_page.html` 로 정적 저장하여 회귀 테스트한다.
  - **services 플래그 매핑** — 22종 화이트리스트 0/1 매핑 + 미관측 신규 코드 등장 시 `services` 컬럼 보존 + stderr WARN 로깅
  - **동 fan-out** — 3개 동 mock(0개·1개·다수 매장 반환) 상황에서 정규화 결과 매장 합 계산
  - **신규 등록 월 결정** (`_latest.csv` 부재 시 부트스트랩 처리 포함, `first_seen_at` 기반 파티션)
  - **동일 매장 재실행** 시 행 갱신 (월 이동 없음)
  - **`_latest.csv` 재작성**: code ASC 정렬, `current_month_file` 컬럼 정확성
  - **API 미관측 매장의 `_latest.csv` 보존** (last_seen_at 직전 값 유지)
  - **트랜잭션 롤백**: 월별 CSV 작성 실패 시 `_latest.csv.tmp` 정리
  - **resultCode != "00000"** 응답 시 즉시 실패
- CI에서 자동 실행

## 워크플로우 흐름

```
[월 04:00 KST] cron 트리거
    ↓
checkout repo (full history)
    ↓
setup Python + install requests + beautifulsoup4
    ↓
python scripts/fetch_gs25.py
  ├─ Step 0: GET /store-services/locations → CSRFToken + cookie jar + sido 17개 파싱
  ├─ Step 2: 각 sido별 GET /searchGungu → 약 250 군구 (0.5초 throttle)
  ├─ Step 3: 각 군구별 GET /searchDong → 약 3,500 동 (0.5초 throttle)
  ├─ Step 4: 각 동별 POST /locationList → json.loads(json.loads(raw)) → 매장 (0.5초 throttle)
  │
  ├─ 정규화 (좌표 swap, services 플래그 매핑, 미지의 신규 코드는 services 컬럼만 채우고 WARN 로깅)
  ├─ convenience/gs25/_latest.csv 1회 로드 (code → row 메모리 맵)
  │    부재 시 빈 맵 (부트스트랩)
  ├─ 매장별 처리:
  │    - _latest에 없음 → 신규: first_seen_at = today, 등록 월 결정 → 월별 파일 append, _latest 맵에 추가
  │    - _latest에 있음 → 갱신: current_month_file 위치의 월별 파일 row 갱신, _latest 맵 갱신
  ├─ 영향받은 월별 CSV 저장
  └─ _latest.csv 통째로 재작성 (code ASC 정렬, atomic rename)
    ↓
python scripts/update_changelog_gs25.py
  └─ git diff convenience/gs25/_latest.csv 분석 → CHANGELOG.md prepend
    ↓
git add + commit (변경 있으면) + push
    ↓
완료
```

## 후속 SPEC (예약)

본 SPEC은 SPEC-EMART24-001 후속 §의 두 번째 체인이다.

- **SPEC-CU-001**: CU 어댑터
- **SPEC-7ELEVEN-001**, **SPEC-MINISTOP-001**: 추가 편의점 체인
- **SPEC-CLOSURE-DETECT-001**: 폐점 자동 추적 (last_seen_at 갱신 중단 감지)
- **SPEC-NOTIFY-001**: 신규 오픈 자동 알림
- **SPEC-CHANGE-VIEWER-001**: 변경 시각화 사이트 (GitHub Pages)
- **SPEC-COMMON-LIB-001**: `scripts/lib/` 공통 모듈 추출 (체인별 어댑터 패턴 표준화 — 본 SPEC 작성 시점에 두 번째 체인이므로 후속에서 본격 분리)

## 위험과 완화

| 위험 | 영향 | 심각도 | 완화 |
|---|---|---|---|
| **API 응답 lat/longs 필드명 의미 반전** | 좌표 swap 누락 시 모든 매장 좌표가 동해상으로 표시되는 데이터 오염 | HIGH | REQ-GS25-005 정규화 코드에 명시 주석 + REQ-GS25-013 단위 테스트 fixture(VQ670)로 회귀 즉시 감지. CI 통과 없이 배포 불가 |
| **이중 JSON 인코딩 변경 가능성** | 응답 파싱 실패로 워크플로우 전면 중단 | MEDIUM | REQ-GS25-013 테스트 fixture가 현재 형태(`json.loads(json.loads(raw))`)를 schema assertion으로 고정. 단일 인코딩으로 변경되면 fixture 단계에서 fail-fast |
| **CSRFToken 형식 변경** | 부트스트랩 실패로 워크플로우 전면 중단 | MEDIUM | REQ-GS25-002 정규식 단위 테스트 + 401/403/500 발생 시 부트스트랩 1회 재시도 후 escalate |
| **GS25 API 인증 정책 강화 (캡차·로그인 요구)** | 수집 불가능 | HIGH | 즉시 워크플로우 실패. 사람이 정책 재검토. 본 SPEC은 인증 회피 시도 금지 |
| **rate limit·차단** | 수집 중단 | MEDIUM | 0.5초 throttle, 백오프, 주 1회 한정, 매너 UA |
| **약관·법적 리스크** | 분쟁 가능 | LOW | 공개 페이지 API만 사용, CC-BY-NC, 원본 저작권 명시. robots.txt 점검 결과 CLAUDE.local.md에 기록 |
| **GH Actions 한도 (45분 timeout)** | 1회 실행 31분 + 여유 → 큰 문제 없음 | LOW | public repo 무제한, timeout 50분으로 설정 |
| **신규 svc_* 코드 등장으로 SPEC 컬럼 누락** | 정보 부분 손실 | LOW | `services` long string 컬럼이 백업 보존, WARN 로그 + Actions summary 노출. SPEC 개정으로 정식 컬럼화 |
| **OPEN_DATE 부재로 인한 emart24와 파티션 키 불일치** | 외부 사용자 혼란 | LOW | README와 본 SPEC에 명시적 안내. emart24는 `OPEN_DATE`, GS25는 `first_seen_at` |
| **월별 CSV와 `_latest.csv` 비동기화** | 신규 판정 오류, 데이터 일관성 손상 | HIGH | REQ-GS25-007/005b 동일 트랜잭션, REQ-GS25-011 atomic rename + 롤백, REQ-GS25-013 테스트 검증 |
| **`_latest.csv` git blob 누적 (1.5만 행 추정)** | 레포 사이즈 증가 | LOW | 텍스트 압축 효과 큼, 5년 누적 시 ~150MB 추정 — public repo 한도 대비 안전 범위 |
| **약 3,500개 POST 호출 중 일부 실패** | 워크플로우 전체 실패, 가용성 저하 | MEDIUM | 호출 단위 백오프 3회 + 누적 401/403/500 5회 시 부트스트랩 재시도. 그래도 실패하는 동이 있으면 즉시 워크플로우 전체 실패 (부분 수집 폐기, 데이터 일관성 우선). 다음 주 자연 재실행으로 흡수 |
| **HTML 마크업 변경으로 정규식 파싱 실패** | 워크플로우 즉시 실패 | MEDIUM | fail-fast + GH 이메일 알림 + REQ-GS25-013 정적 fixture (`gs25_locations_page.html`, `gs25_vq670.json`) 회귀 테스트로 사전 감지 |
| **부분 수집 정책 폐기로 인한 1동 장애 시 전체 실패** | 가용성 저하 | LOW | 다음 주 자연 재실행으로 흡수, 백오프 3회로 일시 장애 흡수 |

## 인수 테스트 시나리오 요약

1. **첫 실행 (부트스트랩)**: 빈 `convenience/gs25/` → 4단계 발견 후 약 1.5만 매장이 단일 월 파일(예: `2026/04.csv`)에 모두 작성 + `_latest.csv` 1.5만 행 신규 생성 (정렬: code ASC, 모든 매장 `first_seen_at = 2026-04-29`)
2. **2주차 실행**: 신규 매장 12건 + 정보 변경 38건 → `2026/05.csv`에 12행 append, 기존 월별 파일에서 38행 갱신, `_latest.csv` 50행이 git diff에 등장
3. **신규 매장**: 직전 `_latest.csv`에 없던 `shopCode`가 등장 → `first_seen_at = today`, `current_month_file = "2026/05"`
4. **매장 정보 변경**: 동일 `shopCode`의 `services`가 변경 → 기존 `current_month_file`의 행 갱신, `last_seen_at = today`, `first_seen_at` 보존, 월 이동 없음
5. **API 일시 장애**: 백오프 3회 후 성공 / 누적 401·403·500 5회 누적 시 부트스트랩 재시도 후 진행
6. **이중 JSON 단일화 회귀**: API 응답이 단일 JSON으로 바뀜 → 테스트 fixture에서 즉시 실패 (CI 차단)
7. **lat/longs 반전 회귀**: 정규화 코드에서 swap이 누락됨 → VQ670 fixture가 lat≈127.04 lng≈37.48로 잘못 계산되어 즉시 실패
8. **신규 svc_* 코드 등장**: 미지의 코드가 `offeringService`에 포함 → `services` 컬럼에 보존되고 stderr `[WARN] unknown service code: <code>` 로그 기록, 워크플로우 정상 종료
9. **CODE 무결성**: `"VQ670"`이 정수로 변환되지 않음 (월별 + `_latest` 모두에서 보존)
10. **API 미관측**: 직전 `_latest.csv`에 있던 매장이 이번 발견 단계에 없음 → `_latest.csv`에 그대로 보존 (last_seen_at 미갱신), 월별 CSV 손대지 않음
11. **트랜잭션 무결성**: 월별 CSV 작성 중 실패 → `_latest.csv.tmp` 폐기, 부분 작성 파일 모두 롤백
12. **CSRFToken 만료**: 워크플로우 도중 401 발생 → 부트스트랩 1회 재시도 후 진행, 그래도 실패면 즉시 실패
13. **rural 군구**: 응답 `result` 배열이 빈 경우 정상 처리 (워크플로우 실패 아님), 해당 군구는 동·매장 호출 건너뜀

## 영향 받는 외부 정책

본 SPEC은 `data-retail` 레포 내부에 한정된다. `itda-skills`의 정책 변경은 필요 없다. SPEC-EMART24-001과 동일하게 `itda-skills/CLAUDE.local.md`의 "데이터 저장 경로 정책"이 본 레포에는 적용되지 않음을 재확인한다 (data-retail은 git 추적 데이터 저장소로 `.itda-skills/`와 무관).

CLAUDE.local.md `robots.txt 점검 기록` 섹션에 GS25 점검 결과를 기록할 예정이다 (구현 시점).
