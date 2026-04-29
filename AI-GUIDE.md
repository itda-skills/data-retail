# AI 어시스턴트 활용 지침 — itda-skills/data-retail

> 이 문서는 Claude / ChatGPT / Cursor / Copilot 등 AI 어시스턴트가 본 데이터셋을 정확히 이해하고 활용할 수 있도록 작성된 **AI 전용 가이드**입니다.
> 본 문서는 단일 소스로 관리되며, raw URL 로 직접 로드하여 사용하세요:
> `https://raw.githubusercontent.com/itda-skills/data-retail/main/AI-GUIDE.md`

---

## 0. 데이터셋 정체성

당신은 `itda-skills/data-retail` 오픈 데이터셋(주간 자동 갱신)에 접근할 수 있다. 이 저장소는 한국 편의점 체인의 매장 정보를 GitHub Actions 로 주 1회 자동 수집·공개하는 시계열 아카이브다. 현재 emart24 약 5,700개 매장이 수록되어 있고, GS25/CU/7-Eleven/미니스톱이 동일 패턴으로 추가될 예정이다.

원본 저작권은 각 체인사에 귀속되며, 데이터는 CC-BY-NC-4.0, 스크립트는 MIT 다.

## 1. 데이터 위치 (UTF-8, RFC 4180 CSV, LF 개행)

- 전체 스냅샷: `https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/_latest.csv`
  - 약 5,700행, 27 컬럼, `code` 오름차순 정렬
- 월별 파일: `emart24/{YYYY}/{MM}.csv` — 각 매장은 본인의 `open_date` 연·월 파일에 1회만 등장
- 컬럼 정의: `https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/README.md`
- 변경 다이제스트: `https://raw.githubusercontent.com/itda-skills/data-retail/main/emart24/CHANGELOG.md`

## 2. 데이터 로드 시 반드시 지킬 것

- `code` 컬럼은 **항상 문자열로 읽는다**. 5자리 zero-pad (예: `"00060"`) 이며, 정수 변환 시 데이터가 손상된다.
- `lat` / `lng` 는 float, `open_date` 는 ISO `YYYY-MM-DD`, `end_date` 는 빈 문자열이면 영업 중이다.
- `svc_*` (12종: parcel, atm, wine, coffee, smoothie, apple, toto, auto, pickup, chicken, noodle) 와 `tobacco_license` 는 `0/1` 컬럼이다.
- `is_24h = 1` 이면 24시간 운영 매장이다.
- `first_seen_at` 은 본 레포가 처음 관측한 일자, `last_seen_at` 은 가장 최근 관측 일자다 — 폐점 추정에 활용 가능.
- `current_month_file` (`_latest.csv` 에만 존재) 은 해당 매장이 위치한 월별 CSV 의 상대 경로 prefix (예: `"2015/03"`).

## 3. 활용 패턴

### 3.1 자연어 분석 요청 예시

- "서울 강남구에 있는 24시간 운영 매장을 위경도와 함께 정리해줘"
- "지난 분기 신규 오픈한 매장 추세를 월별 막대그래프로 그려줘"
- "와인과 ATM 을 동시에 제공하는 매장의 지역 분포를 보여줘"
- "복권(toto) 판매 매장을 지도에 표시해줘"

### 3.2 변경 이력 기반 시계열 질의

`git log emart24/_latest.csv` 의 diff 가 곧 매주 변경 다이제스트다. 다음과 같이 요청할 수 있다.

- "최근 한 달간 emart24/_latest.csv 의 git diff 를 분석해서 신규 매장 목록을 정리해줘"
- "특정 매장 코드의 서비스 플래그 변경 이력을 추적해줘"
- "지난 6개월간 last_seen_at 갱신이 중단된 매장을 폐점 후보로 추려줘"

### 3.3 RAG / 벡터 인덱싱

각 매장 행을 `{title} {address} {svc_*}` 텍스트로 합쳐 임베딩하면 자연어 매장 검색 시스템 (예: "공항 근처 24시간 와인 파는 곳") 을 즉시 구축할 수 있다. `_latest.csv` 를 단일 소스로 사용하라.

### 3.4 좌표 기반 분석

`lat` / `lng` 가 float 으로 제공되므로 별도 지오코딩 없이 반경 검색·클러스터링·heatmap 이 가능하다. 본 레포는 GIS 가공물을 제공하지 않으니 사용자가 직접 처리한다.

## 4. 데이터 한계 — AI 가 미리 알아야 할 사실

- 매장 폐점은 별도 컬럼이 아니라 `last_seen_at` 갱신 중단으로만 추정 가능하다 (정밀 추적은 후속 SPEC).
- `open_date` 가 미래 시점인 예정 오픈 매장이 포함된다. 실제로 오픈하지 않을 수도 있다.
- 일부 비현실적 sentinel 값(예: `OPEN_DATE = 9999-12-31`) 이 API 응답에 존재한다. 분석 시 필터링 권장.
- API 응답 구조 변경 시 수집이 일시 중단될 수 있다 (마지막 성공 실행은 README 배지로 확인).

## 5. 라이선스 / 출처 표기

분석 결과를 외부 공유할 때 다음을 포함하라:

> Source: itda-skills/data-retail (CC-BY-NC-4.0). Original copyright belongs to each convenience store chain.

## 6. 문의

본 데이터셋과 자동화 파이프라인은 **[스킬.잇다 (itda.work)](https://itda.work)** 에서 운영한다. 스킬·Claude 자동화 개발/교육 문의는 `dev@itda.work`.
