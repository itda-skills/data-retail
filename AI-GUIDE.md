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

### 체인별 표준 디렉터리 레이아웃

각 체인 디렉터리는 동일한 5종 파일을 가진다. `{chain}` 자리는 `emart24`, `gs25`, `cu`, `seven_eleven`, `ministop` 등 체인 식별자다.

| 경로 | 내용 |
|---|---|
| `{chain}/_latest.csv` | 전체 매장 평면 스냅샷, 매주 통째로 재작성, `code` 오름차순 정렬 |
| `{chain}/{YYYY}/{MM}.csv` | 신규 등록 월별 분배 — 각 매장은 본인의 `open_date` 연·월 파일에 1회만 등장 |
| `{chain}/README.md` | **그 체인 고유의 컬럼 정의·서비스 플래그 의미** (반드시 먼저 읽을 것) |
| `{chain}/CHANGELOG.md` | 주간 변경 다이제스트 (사람이 읽기용) |

체인별 컬럼·플래그가 일부 다를 수 있다. 분석 전에 해당 체인의 `{chain}/README.md` 를 먼저 로드하라.

예: emart24 의 2025년 12월 파일은 `https://cdn.jsdelivr.net/gh/itda-skills/data-retail@main/emart24/2025/12.csv`

## 2. 모든 체인에 공통으로 적용되는 로드 규칙

다음 규칙은 본 저장소의 모든 체인 CSV 에 공통으로 적용된다. 체인 고유 컬럼은 별도로 `{chain}/README.md` 를 확인하라.

- `code` 컬럼은 **항상 문자열로 읽는다**. zero-pad 정수형 식별자이며, 정수 변환 시 데이터가 손상된다 (예: `"00060"` → `60` 변환 금지).
- `lat` / `lng` 는 float, `open_date` 는 ISO `YYYY-MM-DD`, `end_date` 는 빈 문자열이면 영업 중이다.
- `start_hhmm` / `end_hhmm` 는 `HH:MM` 형식, `is_24h = 1` 이면 24시간 운영 매장이다.
- `svc_*` 로 시작하는 컬럼은 `0/1` 서비스 플래그다. 종류·개수는 체인마다 다르므로 `{chain}/README.md` 참조.
- `first_seen_at` 은 본 레포가 처음 관측한 일자, `last_seen_at` 은 가장 최근 관측 일자다 — 폐점 추정에 활용 가능.
- `current_month_file` (`_latest.csv` 에만 존재) 은 해당 매장이 위치한 월별 CSV 의 상대 경로 prefix (예: `"2015/03"`).

## 3. 활용 패턴

아래 예시의 `{chain}` 자리에는 분석 대상 체인 식별자를 넣는다 (단일 체인일 수도, 복수 체인 비교일 수도 있다).

### 3.1 자연어 분석 요청 예시

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

- 매장 폐점은 별도 컬럼이 아니라 `last_seen_at` 갱신 중단으로만 추정 가능하다 (정밀 추적은 후속 SPEC).
- `open_date` 가 미래 시점인 예정 오픈 매장이 포함될 수 있다 (체인별 정책 차이). 실제로 오픈하지 않을 수도 있다.
- 일부 비현실적 sentinel 값(예: `OPEN_DATE = 9999-12-31`) 이 원천 API 응답에 존재할 수 있다. 분석 시 필터링 권장.
- 원천 API 구조 변경 시 해당 체인의 수집이 일시 중단될 수 있다 (마지막 성공 실행은 README 배지로 확인).

## 5. 라이선스 / 출처 표기

분석 결과를 외부 공유할 때 다음을 포함하라:

> Source: itda-skills/data-retail (CC-BY-NC-4.0). Original copyright belongs to each convenience store chain.

## 6. 문의

본 데이터셋과 자동화 파이프라인은 **[스킬.잇다 (itda.work)](https://itda.work)** 에서 운영한다. 스킬·Claude 자동화 개발/교육 문의는 `dev@itda.work`.
