# GS25 매장 데이터

본 데이터는 GS25 공식 점포찾기 페이지(`gs25.gsretail.com`)에서 자동 수집된 가공물이며,
원본 저작권은 **(주)지에스리테일**에 있습니다.

- **비상업적 사용 권장**, 상업적 사용은 (주)지에스리테일에 직접 문의하시기 바랍니다.
- 라이선스: [CC-BY-NC-4.0](../../LICENSE)
- 수집 스크립트 라이선스: MIT

---

## 갱신 주기

매주 월요일 04:00 KST (GitHub Actions cron `0 19 * * 0` UTC) 자동 갱신.

---

## 파일 구조

```
convenience/gs25/
├── README.md            # 이 파일
├── CHANGELOG.md         # 주간 변경 다이제스트
├── _latest.csv          # 전체 매장 평면 스냅샷 (31컬럼, code ASC)
├── 2026/
│   ├── 04.csv           # 2026년 4월 첫 관측 매장
│   └── 05.csv           # 2026년 5월 신규 관측 매장
└── ...
```

---

## CSV 컬럼 정의

### 월별 CSV (`YYYY/MM.csv`) — 30개 컬럼

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `code` | string | 매장 고유 코드 (예: `"VQ670"`) |
| `title` | string | 매장명 |
| `address` | string | 주소 (도로명·지번 혼재 단일 라인) |
| `lat` | float | **실제 위도** (API `longs` 필드를 swap하여 저장) |
| `lng` | float | **실제 경도** (API `lat` 필드를 swap하여 저장) |
| `services` | string | 서비스 코드 배열을 알파벳순 정렬·세미콜론 join (예: `"atm;cafe25;wine25"`) |
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
| `first_seen_at` | string | ISO 날짜 — 본 레포가 처음 관측한 일자 |
| `last_seen_at` | string | ISO 날짜 — 가장 최근 워크플로우 실행 관측 일자 |

### 최신 스냅샷 (`_latest.csv`) — 31개 컬럼

월별 CSV 30개 컬럼 + `current_month_file` 1개 추가.

| `current_month_file` | string | 해당 매장이 등록된 월별 CSV의 상대 경로 prefix (예: `"2026/04"`) |

---

## 서비스 플래그 (`svc_*`) 의미

| 플래그 | 서비스 내용 |
|---|---|
| `svc_cafe25` | GS25 카페25 |
| `svc_instant` | 즉석식품 |
| `svc_drug` | 의약품 판매 |
| `svc_post` | 우편 서비스 |
| `svc_withdrawal` | 출금 서비스 |
| `svc_atm` | ATM |
| `svc_taxrefund` | 세금 환급 |
| `svc_smart_atm` | 스마트 ATM |
| `svc_self_cooking_utensils` | 셀프 조리 기구 |
| `svc_delivery_service` | 배달 서비스 |
| `svc_parcel_service` | 택배 서비스 |
| `svc_potatoes` | 감자 상품 |
| `svc_cardiac_defi` | 심장충격기(AED) |
| `svc_fish_shaped_bun` | 붕어빵 |
| `svc_wine25` | 와인25 |
| `svc_go_pizza` | 고피자 |
| `svc_spirit_wine` | 양주 판매 |
| `svc_fresh_ganghw` | 강화도 신선식품 |
| `svc_musinsa` | 무신사 상품 |
| `svc_posa` | POSA 카드 |
| `svc_toto` | 토토 |
| `svc_self25` | 셀프25 (무인 점포) |

---

## 좌표 안내 (`lat` / `lng`)

**주의**: GS25 공식 API는 `lat`과 `longs` 필드의 의미가 반전되어 있습니다.
본 CSV는 수집 시 이를 올바르게 swap하여 저장하므로:

- `lat` 컬럼 = **실제 위도 (latitude)**
- `lng` 컬럼 = **실제 경도 (longitude)**

외부 지도 도구(Leaflet, Google Maps 등)에서 `lat`, `lng`을 표준 의미로 사용하면 됩니다.

---

## emart24와의 파티션 키 차이

| | emart24 | GS25 |
|---|---|---|
| **월별 파티션 키** | `OPEN_DATE` (API 제공 오픈일) | `first_seen_at` (본 레포 최초 관측일) |
| **이유** | API가 오픈일을 제공함 | GS25 API는 오픈일 미제공 |

GS25 매장의 `first_seen_at`은 해당 매장이 **이 레포에 처음 등장한 날짜**입니다.
실제 오픈일과 다를 수 있습니다. 두 체인 데이터를 합쳐 분석할 때 이 차이를 반드시 고려하세요.

**부트스트랩(첫 실행) 시**: 모든 기존 매장의 `first_seen_at`은 워크플로우 최초 실행일로 일괄 설정됩니다.
따라서 첫 실행 월(예: `2026/04.csv`)에 전체 매장이 집중됩니다.
이후 주별로 신규 관측 매장만 새 월 파일에 추가됩니다.

---

## Raw URL 사용 예시

```
# 최신 전체 매장 스냅샷
https://raw.githubusercontent.com/{owner}/{repo}/main/convenience/gs25/_latest.csv

# 2026년 4월 최초 관측 매장
https://raw.githubusercontent.com/{owner}/{repo}/main/convenience/gs25/2026/04.csv
```

---

## 알려진 한계

- **오픈일 미제공**: GS25 API는 매장 오픈일을 제공하지 않습니다. `first_seen_at`이 그 대체값입니다.
- **폐점 미추적**: API에서 사라진 매장은 `_latest.csv`에 보존되지만 폐점 여부는 알 수 없습니다. (후속 SPEC-CLOSURE-DETECT-001)
- **영업시간·전화번호 미제공**: GS25 API에서 이 정보를 제공하지 않습니다.
- **부트스트랩 월 편중**: 첫 실행 시 모든 매장이 단일 월 파일에 집중됩니다.

---

## 운영 가이드

### GitHub Actions 실패 알림 설정

워크플로우 실패 시 이메일 알림이 저장소 소유자에게 전송됩니다.

알림이 정상 동작하는지 확인하려면:

1. GitHub → 프로필 아이콘 → **Settings** → **Notifications**
2. **Actions** 섹션에서 "Only notify for failed workflows that I personally triggered" 옵션이 **OFF** 인지 확인
3. OFF이면 모든 실패 워크플로우에 대해 알림을 받습니다

이 확인은 `SPEC-GS25-001` 도입 후 1회 수행하는 것을 권장합니다.
