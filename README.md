# data-retail

국내 편의점 체인 매장 데이터를 GitHub Actions로 주 1회 자동 수집·공개하는 오픈 데이터 저장소입니다.

[![Weekly emart24 Fetch](https://github.com/itda-skills/data-retail/actions/workflows/weekly-emart24.yml/badge.svg)](https://github.com/itda-skills/data-retail/actions/workflows/weekly-emart24.yml)

> 본 프로젝트는 **[스킬.잇다](https://itda.work)** 에서 만들었습니다. 스킬·Claude 자동화 개발/교육 문의는 **dev@itda.work** 로 보내주세요.

## 현재 수집 체인 (sub-category)

| 카테고리 | 체인 | 디렉터리 | 갱신 주기 | 매장 수 |
|---|------|---------|---------|--------|
| convenience (편의점) | emart24 | `convenience/emart24/` | 주 1회 (월 03:00 KST) | ~5,700 |

추후 `convenience/gs25`, `convenience/cu`, `grocery/emart`, `cafe/starbucks` 등으로 확장됩니다.

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

각 파일은 두 호스트로 동일하게 제공됩니다. 일반적으로는 **jsDelivr CDN 을 권장**합니다 — `text/csv` 헤더로 서빙되어 Claude.ai web 등 브라우저 기반 fetch 도구와의 호환성이 좋습니다.

URL 패턴: `https://{host}/itda-skills/data-retail/main/{category}/{chain}/{path}` (jsDelivr 는 `cdn.jsdelivr.net/gh/itda-skills/data-retail@main` prefix).

- **전체 스냅샷 (emart24)**:
  - jsDelivr (권장): `https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/convenience/emart24/_latest.csv`
  - GitHub raw: `https://raw.githubusercontent.com/itda-skills/data-retail/main/convenience/emart24/_latest.csv`
  - 약 5,700행, 27 컬럼, `code` ASC 정렬
- **월별 파일**: 위 URL 패턴에서 `_latest.csv` 자리를 `{YYYY}/{MM}.csv` 로 교체. 한 매장은 본인의 `open_date` 연·월 파일에 1회만 등장합니다.
- **변경 이력**: `git clone` 후 `git log convenience/emart24/_latest.csv` — 매주 자동 커밋된 diff 가 시계열 변경 기록입니다.

> jsDelivr 는 글로벌 CDN 캐시를 사용하므로 갱신이 최대 12시간 지연될 수 있습니다. 실시간 최신값이 필요하면 GitHub raw URL 또는 git clone 을 사용하세요.

## AI 어시스턴트(Claude / ChatGPT 등) 활용

상세 활용 지침은 별도 문서 [`AI-GUIDE.md`](AI-GUIDE.md) 에서 단일 소스로 관리됩니다. 지침이 갱신되어도 raw URL 한 곳만 바뀌므로 자동으로 최신 내용이 전파됩니다.

### AI 에게 한 줄로 컨텍스트 전달

다음 문장을 Claude / ChatGPT / Cursor 등에 그대로 붙여넣으세요.

```
다음 URL의 내용을 먼저 읽고, 안내된 규칙에 따라 데이터셋을 활용해줘:
https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/AI-GUIDE.md
```

### 로컬에서 분석하려면 (Claude Code / Claude Desktop)

Claude Code 의 `/add-dir` 와 MCP filesystem 서버는 **로컬 디렉터리만** 지원합니다. GitHub URL 을 직접 마운트하는 기능은 없으므로 먼저 `git clone` 한 뒤 디렉터리를 추가해주세요.

```bash
git clone https://github.com/itda-skills/data-retail.git
# 이후 Claude Code 에서:
/add-dir /path/to/data-retail
```

clone 한 디렉터리를 추가하면 git 변경 이력까지 분석에 활용할 수 있습니다.

## 디렉터리 구조

```
data-retail/
└── convenience/                   # 카테고리 (sub-category)
    └── emart24/                   # 체인
        ├── README.md              # 컬럼 정의, 서비스 플래그 의미
        ├── CHANGELOG.md           # 주간 변경 다이제스트 (사람이 읽기용)
        ├── _latest.csv            # 전체 매장 스냅샷 (매주 재작성, ~5,700행, 27 컬럼)
        ├── 2008/
        │   ├── 01.csv             # 2008년 1월 오픈 매장
        │   └── ...
        └── 2026/
            ├── 04.csv
            └── 05.csv             # 예정 오픈 매장 포함 가능
```

후속 체인 예: `convenience/gs25/`, `convenience/cu/`, `grocery/emart/`, `cafe/starbucks/` — 동일 디렉터리 패턴을 따릅니다.

## CSV 컬럼 요약

총 26개 (월별 CSV) 또는 27개 (`_latest.csv` 는 `current_month_file` 추가). 자세한 정의는 [`convenience/emart24/README.md`](convenience/emart24/README.md) 참조.

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
