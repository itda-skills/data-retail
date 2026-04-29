---
id: SPEC-EMART24-001
title: emart24 매장 정보 주간 자동 수집 — GitHub Actions + 월별 CSV 누적 + latest snapshot
status: approved
priority: medium
version: 1.2.0
created_at: 2026-04-29
updated_at: 2026-04-29
history:
  - 2026-04-29 v1.2.0: 구현 중 발견된 두 모순 수정 — (a) `_latest.csv` 컬럼 수 26→27 정정 (월별 표는 26개), (b) REQ-EM-004 신규 등록월 규칙을 "OPEN_DATE 월 고정"으로 명확화하여 인수 테스트 #3과 일치
  - 2026-04-29 v1.1.0: latest snapshot(`_latest.csv`) 도입 — 신규 판정 O(1), git diff 가독성 개선 (REQ-EM-004/005 수정, REQ-EM-005b 신설)
  - 2026-04-29 v1.0.0: 초기 SPEC
related:
  - data-retail (this repo)
depends_on: []
references:
  - https://emart24.co.kr/api1/store (공개 엔드포인트, UA + Referer 필요)
  - https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
---

# SPEC-EMART24-001 — emart24 매장 정보 주간 자동 수집

## 배경

`data-retail/` 레포는 국내 주요 편의점 체인의 매장 데이터를 GitHub Actions로 주 1회 자동 수집·공개하는 오픈 데이터 저장소다. 본 SPEC은 첫 체인인 **emart24**의 수집 파이프라인을 정의한다.

emart24는 `https://emart24.co.kr/api1/store` 에서 인증 없이 5,700개 전 매장 정보를 페이지네이션 방식으로 노출하며, 좌표·주소·전화·영업시간·12종 서비스 플래그·오픈일·폐점일·사업자등록 여부를 제공한다. API는 **이미 오픈한 매장과 예정 오픈 매장(미래 OPEN_DATE)을 모두 반환**하므로 단발 크롤만으로도 신규·예정 매장 파악이 가능하다.

상용 지도 서비스(카카오맵·네이버지도)와 차별화되는 가치는 "지점 검색"이 아니라 **매장 시계열 데이터(언제 오픈, 언제 폐점, 서비스 변동)** 의 공개·재현 가능한 아카이브이다. 본 레포는 이를 git 커밋 히스토리 기반으로 구축한다.

## 목표

- emart24 매장 데이터를 주 1회 자동 수집하여 월별 CSV 파일로 누적 저장
- 단순한 폴더 구조로 누구나 raw URL/git clone으로 즉시 사용 가능
- GitHub Actions 무료 한도 내에서 운영 (public repo 무제한)
- 후속 체인(GS25, CU 등)을 동일 패턴으로 추가할 수 있는 디렉터리 구조
- 수집 코드와 데이터 파일이 함께 관리되어 변경 이력 완전 추적

## 비목표

- 실시간/일간 갱신 (주 1회로 충분, 매장 변동성 낮음)
- 좌표 기반 반경 검색·경로 안내 등 GIS 기능 (raw CSV 사용자가 직접 처리)
- 알림(메일·SMS·텔레그램) 발송 (후속 SPEC)
- 데이터 API 서버 (raw CSV 직접 접근으로 충분)
- 카카오/네이버 외부 데이터 cross-validation
- 사용자별 인증·과금 (public repo 무료 운영)

## 데이터 구조

### 디렉터리 레이아웃

```
data-retail/                              (레포 루트)
├── README.md                             # 데이터 사용법, 라이선스, 갱신 주기
├── LICENSE                               # CC-BY-NC-4.0 (데이터)
├── .github/
│   └── workflows/
│       └── weekly-emart24.yml            # cron: 매주 월요일 03:00 KST
├── scripts/
│   ├── fetch_emart24.py                  # API → 정규화 → 월별 CSV append
│   ├── update_changelog.py               # 주간 다이제스트 → CHANGELOG.md
│   ├── requirements.txt                  # requests
│   └── tests/
│       └── test_fetch_emart24.py
└── emart24/
    ├── README.md                         # CSV 컬럼 정의, 서비스 플래그 의미
    ├── CHANGELOG.md                      # 주간 변경 다이제스트 (사람이 읽기용)
    ├── _latest.csv                       # 전체 매장 평면 스냅샷 (매주 통째로 재작성, 신규 판정 소스)
    ├── 2007/
    │   └── 06.csv
    ├── 2008/
    │   ├── 01.csv
    │   └── 02.csv
    ├── ...
    ├── 2026/
    │   ├── 04.csv
    │   └── 05.csv                        # 예정 오픈 매장 포함 가능
    └── ...
```

### 월별 CSV 규칙 (REQ-EM-005 참조)

- 파일명: `emart24/{YYYY}/{MM}.csv` (월 2자리 zero-padded)
- 한 매장은 **본인의 "신규 등록 월" 파일에 1회만 등장**
- "신규 등록 월" = **항상 매장의 `OPEN_DATE` 연·월** (예: OPEN_DATE=`2015-03-12` → `2015/03.csv`, OPEN_DATE=`2026-05-25` → `2026/05.csv`)
- `first_seen_at` 컬럼은 별도 차원으로 본 레포가 처음 관측한 일자를 보존하며 등록월 결정에 영향 없음
- 두 시점이 다를 수 있는 경우 (참고):
  - **OPEN_DATE < first_seen** (오래된 매장이 뒤늦게 API에 잡힘): 파일은 `2015/03.csv`, `first_seen_at`은 늦은 관측일
  - **OPEN_DATE > first_seen** (예정 오픈 매장이 미리 노출): 파일은 `2026/05.csv` (미래 월), `first_seen_at`은 이른 관측일
  - **OPEN_DATE == first_seen**: 동일 월

### CSV 컬럼 정의

본 표는 **월별 CSV**의 컬럼 정의 (총 26개 컬럼)이다. `_latest.csv`는 본 표 26개 + `current_month_file` 1개 = 총 27개 컬럼 (Latest Snapshot 규칙 참조).

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `code` | string | API의 `CODE`, 5자리 zero-padded — 고유 식별자 |
| `title` | string | 매장명 |
| `address` | string | 도로명 주소 |
| `address_detail` | string | 상세 주소 (없으면 빈 문자열) |
| `phone` | string | 전화번호 |
| `lat` | float | 위도 |
| `lng` | float | 경도 |
| `open_date` | string | ISO `YYYY-MM-DD` |
| `end_date` | string | 폐점일 ISO 또는 빈 문자열 |
| `start_hhmm` | string | `HH:MM` |
| `end_hhmm` | string | `HH:MM` |
| `is_24h` | int | 0/1 |
| `svc_parcel` | int | 0/1 |
| `svc_atm` | int | 0/1 |
| `svc_wine` | int | 0/1 |
| `svc_coffee` | int | 0/1 |
| `svc_smoothie` | int | 0/1 |
| `svc_apple` | int | 0/1 (원본 SVR_APPLE 보존) |
| `svc_toto` | int | 0/1 |
| `svc_auto` | int | 0/1 |
| `svc_pickup` | int | 0/1 |
| `svc_chicken` | int | 0/1 |
| `svc_noodle` | int | 0/1 |
| `tobacco_license` | int | 0/1 |
| `first_seen_at` | string | ISO 날짜 — 본 레포가 처음 관측한 일자 |
| `last_seen_at` | string | ISO 날짜 — 가장 최근 워크플로우 실행 관측 일자 |

### Latest Snapshot 규칙 (`emart24/_latest.csv`, REQ-EM-005b 참조)

- 위치: `emart24/_latest.csv` (체인 디렉터리 루트)
- 내용: 본 레포가 관측한 **전체 매장 평면 목록** (5,700여 행)
- 매주 워크플로우 실행 시 **통째로 재작성** (append 아님, 정렬 키: `code` ASC)
- 컬럼: 월별 CSV와 동일 (위 표) + 다음 1개 추가
  - `current_month_file` (string): 해당 매장이 등록된 월별 CSV의 상대 경로 prefix (예: `"2015/03"`, `"2026/05"`)
- 포함 대상:
  - API에서 관측된 모든 매장
  - **이번 실행에서 미관측이지만 이전에 관측된 매장도 유지** (last_seen_at만 과거 값 보존, 폐점 추적은 후속 SPEC)
- 용도:
  - 신규 매장 판정 소스 (REQ-EM-004): 매주 시작 시 `_latest.csv` 1회 로드 → `code → row` 맵 → O(1) 룩업
  - 변경 다이제스트 생성 소스 (REQ-EM-006): `git diff _latest.csv` 단일 파일 분석으로 신규/갱신/미관측 분류
  - 외부 사용자의 "현재 전체 매장 1회 다운로드" 진입점

### 인코딩

UTF-8 (BOM 없음). LF 개행. RFC 4180 준수.

## 요구사항 (EARS)

### REQ-EM-001 (Time-driven) — 주간 자동 실행

WHEN the GitHub Actions cron schedule fires every Monday at 03:00 KST, the system SHALL execute the full fetch pipeline.

**Acceptance criteria:**
- cron 표현식: `0 18 * * 0` (UTC 일요일 18:00 = KST 월요일 03:00)
- 워크플로우 파일: `.github/workflows/weekly-emart24.yml`
- 수동 트리거 지원 (`workflow_dispatch`)
- 실행 환경: `ubuntu-latest`, Python 3.14+
- 실행 시간 5분 이내 정상 완료

### REQ-EM-002 (Ubiquitous) — emart24 API 수집

The system SHALL retrieve all stores from the emart24 public API and normalize them to the CSV schema.

**Acceptance criteria:**
- 엔드포인트: `https://emart24.co.kr/api1/store`
- 헤더: `User-Agent` (Windows Chrome), `Referer: https://emart24.co.kr/store`, `X-Requested-With: XMLHttpRequest`
- 페이지네이션: `page` 파라미터, 페이지당 40건, 첫 응답 `count` 필드로 총 페이지 산출
- 페이지 간 0.5초 sleep
- 5xx/타임아웃 시 지수 백오프 재시도 3회 (1s → 2s → 4s)
- 4xx 즉시 실패
- 정규화:
  - `LATITUDE`/`LONGITUDE` string → float
  - `OPEN_DATE: "2008.01.28"` → `"2008-01-28"`
  - `END_DATE: "9999.12.31"` → 빈 문자열
  - `START_HHMM: "0600"` → `"06:00"`
  - `is_24h = 1 if (SVR_24 == 1 or (start == end == "0000")) else 0`
  - 12개 SVR_* 필드를 `svc_*` 0/1 컬럼으로 매핑
  - `ADDRESS_DE` 부재 시 `address_detail`은 빈 문자열

### REQ-EM-003 (Ubiquitous) — 식별자 보존

The system SHALL use `CODE` as the primary key and preserve its 5-digit zero-padded string format throughout the pipeline.

**Acceptance criteria:**
- CSV에 `code` 컬럼은 항상 따옴표로 감싸서 출력
- 정수로 변환 금지
- 같은 실행 내 중복 `code` 발견 시 워크플로우 실패 처리

### REQ-EM-004 (Event-driven) — 신규 매장 판정

WHEN the fetch completes, the system SHALL determine the "new month" file destination for each store using `_latest.csv` as the single source of truth.

**Acceptance criteria:**
- 판정 소스: `emart24/_latest.csv` 1회 로드 → `code → row` 메모리 맵 (O(1) 룩업)
  - `_latest.csv` 부재(부트스트랩 첫 실행) 시: 빈 맵으로 시작, 모든 매장은 신규로 분류
  - 월별 CSV는 판정 소스로 사용하지 않음 (폴백·검증 시에만 스캔)
- 매장의 신규 등록 월 = **항상 `open_date.year/month`** (first_seen_at은 등록월 결정에 사용하지 않으며 별도 컬럼으로 보존)
- `first_seen_at`은 다음 규칙으로 결정:
  - `_latest.csv`에 해당 `code`가 없으면 → 오늘 날짜 (워크플로우 실행일)
  - 있으면 → 기존 row의 `first_seen_at` 보존
- `current_month_file`:
  - 신규: 새로 결정한 등록 월(예: `"2026/05"`)
  - 기존: `_latest.csv`의 기존 값 보존 (월 이동 없음, REQ-EM-005)
- 결과 매장 분류 출력 (콘솔 로그용):
  - `coming_soon`: `open_date > today`
  - `recently_opened`: `today - 30일 ≤ open_date ≤ today`
  - `existing`: 그 외

### REQ-EM-005 (Event-driven) — 월별 CSV 작성/갱신

WHEN store data is normalized, the system SHALL write each store to exactly one monthly CSV file based on its new-month destination.

**Acceptance criteria:**
- 각 매장은 본인의 신규 등록 월 파일에 정확히 한 번만 존재
- 같은 매장이 이전 월 파일에서 발견되면 그 파일에서 행을 갱신 (월 이동 없음)
  - 갱신 대상 필드: `title`, `address`, `phone`, `lat/lng`, `end_date`, `start_hhmm`/`end_hhmm`, `is_24h`, 모든 `svc_*`, `tobacco_license`, `last_seen_at`
  - 보존 필드: `code`, `open_date`, `first_seen_at`
- 새 매장은 신규 등록 월 파일에 append (파일이 없으면 디렉터리·파일 생성)
- API 응답에서 사라진 매장은 삭제하지 않음 (마지막 `last_seen_at` 유지) — 폐점 추적은 후속 SPEC
- CSV 컬럼 순서는 본 SPEC의 "CSV 컬럼 정의" 표 그대로 고정 (월별 CSV는 `current_month_file` 컬럼 미포함)
- 월별 CSV 갱신과 `_latest.csv` 재작성은 **동일 트랜잭션** — 둘 중 하나만 성공해서는 안 됨 (REQ-EM-010 롤백 정책)

### REQ-EM-005b (Event-driven) — Latest Snapshot 재작성

WHEN store data is normalized, the system SHALL rewrite `emart24/_latest.csv` from scratch with the current full store population.

**Acceptance criteria:**
- 위치: `emart24/_latest.csv`
- 매주 **통째로 재작성** (in-place 갱신 아님, 임시파일 → atomic rename)
- 정렬: `code` ASC (안정적 git diff 보장)
- 행 구성:
  - 이번 실행에서 API 관측된 모든 매장 (정규화된 최신 값, `last_seen_at = today`)
  - 이전에 관측되었으나 이번 실행에 미관측된 매장도 보존 (`last_seen_at`은 직전 값 유지)
- 컬럼: "CSV 컬럼 정의" 표 26개 + `current_month_file` 1개 = 27개
  - `current_month_file`: 해당 매장이 위치한 월별 CSV의 상대 경로 prefix (예: `"2015/03"`)
  - 신규 매장: REQ-EM-004에서 결정된 신규 등록 월
  - 기존 매장: 직전 `_latest.csv`의 값 보존 (월 이동 금지)
- 부트스트랩(첫 실행): `_latest.csv`가 없으면 새로 생성. 모든 매장은 신규로 처리
- 무결성: 같은 실행 내 `code` 중복 시 워크플로우 실패 (REQ-EM-003)

### REQ-EM-006 (Event-driven) — 변경 다이제스트 작성

WHEN the monthly CSVs are updated, the system SHALL append a weekly digest entry to `emart24/CHANGELOG.md`.

**Acceptance criteria:**
- 형식 (역순 시간 정렬, 최신이 위):

```
## 2026-04-29 (주간 갱신)

- 신규 등록: 12개 (2026/04 +5, 2026/05 +7)
  - 신규 매장 일부: 가산디지털점, 동탄2신도시점, ...
- 정보 갱신: 38개 매장 (서비스 플래그 22, 영업시간 11, 주소 5)
- API 미관측: 3개 매장 — 폐점/이전 가능성

실행: actions run #42
```

- 신규 매장 목록은 최대 10개까지 표시, 초과 시 "외 N개"
- 정보 갱신은 카운트만 (개별 diff는 git diff)
- 실행 링크는 GitHub Actions 환경변수 (`GITHUB_RUN_ID`, `GITHUB_REPOSITORY`)에서 추출
- 다이제스트 분석 소스: `git diff HEAD~1 -- emart24/_latest.csv` 단일 파일 분석
  - 추가된 row → 신규 등록 (code 기준)
  - 변경된 row → 정보 갱신 (변경 필드 카운트)
  - 직전 값 대비 `last_seen_at`이 갱신되지 않은 row → API 미관측 (이번 실행에서 재발견 안됨)

### REQ-EM-007 (Event-driven) — 자동 커밋

WHEN updates are written, the system SHALL commit and push changes via the workflow.

**Acceptance criteria:**
- 커밋 작성자: `github-actions[bot]`
- 커밋 메시지: `chore(emart24): weekly fetch {YYYY-MM-DD} — 신규 N, 갱신 M, 미관측 K`
- 변경 사항이 없으면 커밋하지 않음
- `[skip ci]` 플래그 포함하여 무한 루프 방지
- main 브랜치에 직접 push (PR 없이)

### REQ-EM-008 (Ubiquitous) — 매너 throttle

The system SHALL be a polite client to the upstream API.

**Acceptance criteria:**
- 페이지 간 기본 0.5초, `--delay` CLI 인자로 조정 가능
- 1회 풀 크롤은 약 5,700건 / 40 = 143페이지 × 0.5초 ≈ 1.5분
- robots.txt 점검 결과를 README에 명시

### REQ-EM-009 (Ubiquitous) — 라이선스와 사용 안내

The system SHALL document data licensing and attribution clearly.

**Acceptance criteria:**
- 레포 루트 `LICENSE`: CC-BY-NC-4.0 (데이터)
- `README.md`:
  - "본 데이터는 emart24 공식 점포찾기 API에서 자동 수집된 가공물이며, 원본 저작권은 이마트24(주)에 있습니다." 명시
  - 비상업적 사용 권장, 상업적 사용은 직접 문의
  - 갱신 주기, 컬럼 정의, 알려진 한계
  - raw URL 사용 예시
- `scripts/` 코드는 별도 MIT 라이선스 (소스/데이터 라이선스 분리)

### REQ-EM-010 (Ubiquitous) — 워크플로우 실패 가시성

The system SHALL surface failures clearly without breaking the data.

**Acceptance criteria:**
- API 실패·재시도 소진 시 워크플로우 exit code 1
- 정규화 실패·중복 code 발견 시 즉시 실패하고 부분 작성된 파일 롤백 (commit 안 함)
- 롤백 범위: 영향받은 월별 CSV + `_latest.csv` 모두. 둘 중 하나만 갱신된 상태로 종료 금지
- `_latest.csv`는 임시파일(`_latest.csv.tmp`)에 먼저 작성한 뒤 atomic rename으로 교체. rename 실패 시 임시파일 삭제
- 워크플로우 실패 시 GitHub의 기본 알림 사용
- 마지막 성공 실행일을 README 배지로 표기

### REQ-EM-011 (Ubiquitous) — 테스트

The system SHALL include unit tests for normalization and monthly file routing logic.

**Acceptance criteria:**
- `scripts/tests/test_fetch_emart24.py`
- mock HTTP fixture (실 API 호출 없음)
- 테스트 항목:
  - `OPEN_DATE` 정규화
  - `END_DATE: "9999.12.31"` → 빈 문자열
  - `is_24h` 계산
  - `code` 보존
  - 신규 등록 월 결정 로직 (`_latest.csv` 부재 시 부트스트랩 처리 포함)
  - 동일 매장 재실행 시 행 갱신 (월 이동 없음)
  - `_latest.csv` 재작성: code ASC 정렬, `current_month_file` 컬럼 정확성
  - API 미관측 매장의 `_latest.csv` 보존 (last_seen_at 직전 값 유지)
  - 트랜잭션 롤백: 월별 CSV 작성 실패 시 `_latest.csv.tmp` 정리
- CI에서 자동 실행

## 워크플로우 흐름

```
[월 03:00 KST] cron 트리거
    ↓
checkout repo (full history)
    ↓
setup Python + install requests
    ↓
python scripts/fetch_emart24.py
  ├─ API 페이지 1~143 순회
  ├─ 정규화 (Store row 5,700개)
  ├─ emart24/_latest.csv 1회 로드 (CODE → row 메모리 맵, O(1) 룩업)
  │    - 부재 시 빈 맵으로 시작 (부트스트랩)
  ├─ 매장별 처리:
  │    - _latest에 없음 → 신규: 등록 월 결정 → 월별 파일에 append, _latest 맵에 추가
  │    - _latest에 있음 → 갱신: current_month_file 위치의 월별 파일 row 갱신, _latest 맵 갱신
  ├─ 영향받은 월별 CSV 저장
  └─ _latest.csv 통째로 재작성 (code ASC 정렬, atomic rename)
    ↓
python scripts/update_changelog.py
  └─ git diff 분석 → CHANGELOG.md에 다이제스트 prepend
    ↓
git add + commit (변경 있으면) + push
    ↓
완료
```

## 후속 SPEC (예약)

- **SPEC-GS25-001**: GS25 어댑터
- **SPEC-CU-001**: CU 어댑터
- **SPEC-7ELEVEN-001**, **SPEC-MINISTOP-001**
- **SPEC-CLOSURE-DETECT-001**: 폐점 자동 추적
- **SPEC-NOTIFY-001**: 신규 오픈 자동 알림
- **SPEC-CHANGE-VIEWER-001**: 변경 시각화 사이트 (GitHub Pages)

## 위험과 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| emart24 API 응답 구조 변경 | 워크플로우 실패 | 알 수 없는 필드 무시, 알려진 필드만 사용. 실패 시 사람이 인지 |
| API rate limit·차단 | 수집 중단 | 0.5초 throttle, 백오프, 주 1회 한정 |
| 약관·법적 리스크 | 분쟁 가능 | 공개 API만 사용, CC-BY-NC, 원본 저작권 명시 |
| GH Actions 한도 | 실행 실패 | public repo는 무제한 |
| 동일 매장의 월 이동 | 데이터 무결성 손상 | REQ-EM-005 명시: 매장은 신규 등록 월에 고정 |
| 미래 OPEN_DATE 매장 신뢰성 | 실제 오픈 안 할 수 있음 | CSV에 그대로 보존, 사용자가 필터 |
| 월별 CSV와 `_latest.csv` 비동기화 | 신규 판정 오류, 데이터 일관성 손상 | REQ-EM-005/005b 동일 트랜잭션, REQ-EM-010 atomic rename + 롤백, REQ-EM-011 테스트 검증 |
| `_latest.csv` 1.4MB git blob 누적 | 레포 사이즈 증가 | git LFS 불필요(텍스트 압축 효과 큼), 5년 누적 시 ~50MB 추정 — public repo 한도(1GB) 대비 무시할 수준 |

## 인수 테스트 시나리오 요약

1. **첫 실행 (부트스트랩)**: 빈 레포 → 5,700개 매장이 본인의 OPEN_DATE 월 파일에 분배 작성 + `_latest.csv` 5,700행 신규 생성 (정렬: code ASC)
2. **2주차 실행**: 정보 변경 38건 + 신규 12건 → 월별 파일 12개 추가/38개 갱신, `_latest.csv` 50행이 git diff에 등장 (추가 12 + 수정 38)
3. **예정 오픈**: `OPEN_DATE = 2026-05-25` 매장이 4월 실행에 노출 → `2026/05.csv`에 작성, `_latest.csv`에 `current_month_file = "2026/05"`, `first_seen_at = 2026-04-29`
4. **API 일시 장애**: 백오프 후 성공
5. **API 응답 구조 변경**: 새 SVR_* 필드 등장 → 무시, 데이터는 정상
6. **변경 없는 주**: 월별 CSV·`_latest.csv` 모두 변경 없음 → 빈 커밋·CHANGELOG 갱신 안 함
7. **CODE 무결성**: `"00060"`이 정수로 변환되지 않음 (월별 + `_latest` 모두에서 보존)
8. **API 미관측**: 직전 `_latest.csv`에 있던 매장이 이번 API에 없음 → `_latest.csv`에 그대로 보존 (last_seen_at 미갱신), 월별 CSV는 손대지 않음
9. **트랜잭션 무결성**: 월별 CSV 작성 중 실패 → `_latest.csv`도 롤백, 부분 작성된 파일 모두 폐기

## 영향 받는 외부 정책

본 SPEC은 `data-retail` 레포 내부에 한정. `itda-skills` 의 정책 변경은 필요 없음. `itda-skills/CLAUDE.local.md` 의 "데이터 저장 경로 정책"이 본 레포에는 적용되지 않음을 명확히 한다 (data-retail은 git 추적 데이터 저장소, `.itda-skills/` 와 무관).
