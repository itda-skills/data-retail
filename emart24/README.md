# emart24 데이터 가이드

## 파일 구조

| 파일 | 설명 |
|------|------|
| `_latest.csv` | 전체 매장 평면 스냅샷. 매주 통째로 재작성. code ASC 정렬. |
| `CHANGELOG.md` | 주간 변경 다이제스트 (사람이 읽기용). |
| `{YYYY}/{MM}.csv` | 월별 누적 파일. 해당 월이 신규 등록월인 매장만 포함. |

## `_latest.csv` 설명

- **용도**: 전체 매장 1회 다운로드, 신규 판정 기준점, git diff 가독성
- **갱신**: 매주 통째로 재작성 (append 아님)
- **정렬**: `code` ASC
- **포함 대상**: 이번 주 API 관측 매장 + 미관측이지만 과거에 관측된 매장 (폐점 추적용)

## 월별 CSV 규칙

- 각 매장은 **정확히 하나의 월별 파일**에만 등장합니다.
- 신규 등록 월 = `min(OPEN_DATE월, 첫 관측월)`. 단, 예정 오픈 매장은 OPEN_DATE 기준 미래 월에 배치됩니다.
- 한번 배치된 매장은 월별 파일을 이동하지 않습니다 (정보 갱신은 동일 파일 내 행 갱신).

## CSV 컬럼 정의 (월별 CSV: 26개)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `code` | string | 5자리 zero-padded 고유 식별자 (예: `"00060"`) |
| `title` | string | 매장명 |
| `address` | string | 도로명 주소 |
| `address_detail` | string | 상세 주소 (없으면 빈 문자열) |
| `phone` | string | 전화번호 |
| `lat` | float | 위도 |
| `lng` | float | 경도 |
| `open_date` | string | 오픈일 ISO 형식 `YYYY-MM-DD` |
| `end_date` | string | 폐점일 ISO 형식, 또는 빈 문자열 (미정) |
| `start_hhmm` | string | 영업 시작 시각 `HH:MM` |
| `end_hhmm` | string | 영업 종료 시각 `HH:MM` |
| `is_24h` | int (0/1) | 24시간 영업 여부 |
| `svc_parcel` | int (0/1) | 택배 서비스 |
| `svc_atm` | int (0/1) | ATM 서비스 |
| `svc_wine` | int (0/1) | 와인 판매 |
| `svc_coffee` | int (0/1) | 커피 서비스 |
| `svc_smoothie` | int (0/1) | 스무디 서비스 |
| `svc_apple` | int (0/1) | Apple 제품 판매 (SVR_APPLE 원본 보존) |
| `svc_toto` | int (0/1) | 스포츠 토토 |
| `svc_auto` | int (0/1) | 자동화 서비스 |
| `svc_pickup` | int (0/1) | 픽업 서비스 |
| `svc_chicken` | int (0/1) | 치킨 서비스 |
| `svc_noodle` | int (0/1) | 라면 서비스 |
| `tobacco_license` | int (0/1) | 담배 판매 허가 |
| `first_seen_at` | string | 본 레포가 처음 관측한 날짜 `YYYY-MM-DD` |
| `last_seen_at` | string | 가장 최근 워크플로우 실행 관측 날짜 `YYYY-MM-DD` |

## `_latest.csv` 추가 컬럼 (총 27개)

위 26개 컬럼에 다음 1개가 추가됩니다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `current_month_file` | string | 해당 매장이 등록된 월별 CSV의 상대 경로 prefix (예: `"2015/03"`) |

## 서비스 플래그 의미

- `is_24h = 1`: 24시간 영업. API의 `SVR_24=1` 또는 영업시간이 `0000-0000` 인 경우.
- `svc_*`: 0=미제공, 1=제공. API의 `SVR_*` 필드를 직접 매핑.

## 인코딩 규칙

- 인코딩: UTF-8 (BOM 없음)
- 개행: LF (`\n`)
- 형식: RFC 4180 준수
- `code` 컬럼: 항상 따옴표로 감싸서 출력 (`"00060"`)
