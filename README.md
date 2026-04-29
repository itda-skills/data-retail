# data-retail

국내 편의점 체인 매장 데이터를 GitHub Actions로 주 1회 자동 수집·공개하는 오픈 데이터 저장소입니다.

![Last Fetch](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2F{OWNER}%2F{REPO}%2Factions%2Fworkflows%2Fweekly-emart24.yml%2Fruns%3Fstatus%3Dsuccess%26per_page%3D1&query=%24.workflow_runs%5B0%5D.updated_at&label=마지막%20수집&color=green)

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
# 전체 최신 스냅샷 (1회 다운로드용)
curl -O https://raw.githubusercontent.com/{OWNER}/{REPO}/main/emart24/_latest.csv

# 특정 월 데이터
curl -O https://raw.githubusercontent.com/{OWNER}/{REPO}/main/emart24/2026/04.csv
```

### pandas로 읽기

```python
import pandas as pd

# 최신 스냅샷
df = pd.read_csv(
    "https://raw.githubusercontent.com/{OWNER}/{REPO}/main/emart24/_latest.csv",
    dtype={"code": str},  # code 컬럼을 문자열로 읽어야 zero-pad 보존
)

# 특정 월
df_april = pd.read_csv(
    "https://raw.githubusercontent.com/{OWNER}/{REPO}/main/emart24/2026/04.csv",
    dtype={"code": str},
)
```

## 디렉터리 구조

```
emart24/
├── README.md          # 컬럼 정의
├── CHANGELOG.md       # 주간 변경 다이제스트
├── _latest.csv        # 전체 매장 스냅샷 (매주 재작성, ~5,700행)
├── 2008/
│   ├── 01.csv         # 2008년 1월 오픈 매장
│   └── ...
└── 2026/
    ├── 04.csv
    └── 05.csv         # 예정 오픈 매장 포함 가능
```

## 알려진 한계

- 매장 폐점 추적은 `last_seen_at` 컬럼으로 근사값만 제공됩니다 (상세 추적은 후속 SPEC).
- 예정 오픈 매장(`open_date > 오늘`)이 실제로 오픈하지 않을 수 있습니다.
- API 구조 변경 시 수집이 중단될 수 있습니다. 이슈를 통해 알려주세요.

## 기여

SPEC 문서: `.moai/specs/SPEC-EMART24-001/spec.md`

후속 체인 추가, 버그 제보, 데이터 활용 사례는 이슈 또는 PR을 통해 기여해 주세요.
