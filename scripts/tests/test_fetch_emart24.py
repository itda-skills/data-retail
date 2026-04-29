"""
SPEC-EMART24-001 단위 테스트
emart24 매장 정보 수집 파이프라인의 핵심 로직을 검증한다.
실제 API 호출 없이 mock fixture를 사용한다.
"""

import csv
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch


# 테스트 대상 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetch_emart24 import (
    decide_destination,
    normalize_store,
    rewrite_latest_csv,
)

# ---------------------------------------------------------------------------
# 공통 fixture
# ---------------------------------------------------------------------------

RAW_STORE_BASE = {
    "CODE": "00060",
    "TITLE": "테스트점",
    "ADDRESS": "서울시 강남구 테헤란로 1",
    "ADDRESS_DE": "101호",
    "TEL": "02-1234-5678",
    "LATITUDE": "37.5000",
    "LONGITUDE": "127.0000",
    "OPEN_DATE": "2008.01.28",
    "END_DATE": "9999.12.31",
    "START_HHMM": "0000",
    "END_HHMM": "0000",
    "SVR_24": "1",
    "SVR_PARCEL": "1",
    "SVR_ATM": "0",
    "SVR_WINE": "0",
    "SVR_COFFEE": "1",
    "SVR_SMOOTHIE": "0",
    "SVR_APPLE": "0",
    "SVR_TOTO": "0",
    "SVR_AUTO": "0",
    "SVR_PICKUP": "1",
    "SVR_CHICKEN": "0",
    "SVR_NOODLE": "0",
    "BUSINESS_LICENSE": "1",
}

# 정규화된 매장 행 (월별 CSV용)
NORMALIZED_COLUMNS = [
    "code",
    "title",
    "address",
    "address_detail",
    "phone",
    "lat",
    "lng",
    "open_date",
    "end_date",
    "start_hhmm",
    "end_hhmm",
    "is_24h",
    "svc_parcel",
    "svc_atm",
    "svc_wine",
    "svc_coffee",
    "svc_smoothie",
    "svc_apple",
    "svc_toto",
    "svc_auto",
    "svc_pickup",
    "svc_chicken",
    "svc_noodle",
    "tobacco_license",
    "first_seen_at",
    "last_seen_at",
]

LATEST_COLUMNS = NORMALIZED_COLUMNS + ["current_month_file"]


# ---------------------------------------------------------------------------
# T01: OPEN_DATE 정규화 — "2008.01.28" → "2008-01-28"
# ---------------------------------------------------------------------------


def test_T01_open_date_normalization():
    """REQ-EM-002: OPEN_DATE 점(.) 구분자를 ISO 하이픈(-)으로 정규화한다."""
    raw = dict(RAW_STORE_BASE)
    raw["OPEN_DATE"] = "2008.01.28"

    result = normalize_store(raw)

    assert result["open_date"] == "2008-01-28", (
        f"OPEN_DATE '2008.01.28'은 '2008-01-28'로 정규화되어야 한다. 실제: {result['open_date']}"
    )


# ---------------------------------------------------------------------------
# T02: END_DATE 정규화 — "9999.12.31" → 빈 문자열
# ---------------------------------------------------------------------------


def test_T02_end_date_sentinel_to_empty():
    """REQ-EM-002: END_DATE '9999.12.31'은 폐점일 미정으로, 빈 문자열로 정규화한다."""
    raw = dict(RAW_STORE_BASE)
    raw["END_DATE"] = "9999.12.31"

    result = normalize_store(raw)

    assert result["end_date"] == "", (
        f"END_DATE '9999.12.31'은 빈 문자열이어야 한다. 실제: {result['end_date']}"
    )


def test_T02b_end_date_real_date_preserved():
    """END_DATE에 실제 폐점일이 있으면 ISO 형식으로 보존한다."""
    raw = dict(RAW_STORE_BASE)
    raw["END_DATE"] = "2023.06.30"

    result = normalize_store(raw)

    assert result["end_date"] == "2023-06-30"


# ---------------------------------------------------------------------------
# T03: is_24h 계산
# ---------------------------------------------------------------------------


def test_T03_is_24h_svr24_flag():
    """REQ-EM-002: SVR_24=1 이면 is_24h=1."""
    raw = dict(RAW_STORE_BASE)
    raw["SVR_24"] = "1"
    raw["START_HHMM"] = "0600"
    raw["END_HHMM"] = "2200"

    result = normalize_store(raw)

    assert result["is_24h"] == 1


def test_T03b_is_24h_start_end_zero():
    """REQ-EM-002: SVR_24=0 이라도 start==end=='0000' 이면 is_24h=1."""
    raw = dict(RAW_STORE_BASE)
    raw["SVR_24"] = "0"
    raw["START_HHMM"] = "0000"
    raw["END_HHMM"] = "0000"

    result = normalize_store(raw)

    assert result["is_24h"] == 1


def test_T03c_is_24h_false():
    """REQ-EM-002: SVR_24=0 이고 start!=end='0000' 이 아니면 is_24h=0."""
    raw = dict(RAW_STORE_BASE)
    raw["SVR_24"] = "0"
    raw["START_HHMM"] = "0600"
    raw["END_HHMM"] = "2200"

    result = normalize_store(raw)

    assert result["is_24h"] == 0


# ---------------------------------------------------------------------------
# T04: code zero-padding 5자리 보존
# ---------------------------------------------------------------------------


def test_T04_code_zero_padding_preserved():
    """REQ-EM-003: CODE는 5자리 zero-padded 문자열로 보존한다. 정수 변환 금지."""
    raw = dict(RAW_STORE_BASE)
    raw["CODE"] = "00060"

    result = normalize_store(raw)

    assert result["code"] == "00060", (
        f"code는 문자열 '00060'이어야 한다. 실제: {result['code']!r}"
    )
    assert isinstance(result["code"], str), "code 타입이 str이어야 한다."


def test_T04b_code_written_quoted(tmp_path):
    """REQ-EM-003: CSV 파일에서 code는 항상 따옴표로 감싸서 출력한다."""
    raw = dict(RAW_STORE_BASE)
    store = normalize_store(raw)
    store["first_seen_at"] = "2026-04-29"
    store["last_seen_at"] = "2026-04-29"
    store["current_month_file"] = "2008/01"

    latest_path = tmp_path / "emart24" / "_latest.csv"
    latest_path.parent.mkdir(parents=True)

    rewrite_latest_csv([store], latest_path)

    content = latest_path.read_text(encoding="utf-8")
    # code 값 "00060"이 따옴표로 감싸졌는지 확인
    assert '"00060"' in content, (
        f"code '00060'이 따옴표로 감싸져야 한다. 파일 내용:\n{content[:200]}"
    )


# ---------------------------------------------------------------------------
# T05: 신규 매장 등록월 결정 — _latest.csv 부재(부트스트랩)
# ---------------------------------------------------------------------------


def test_T05_bootstrap_no_latest_csv():
    """REQ-EM-004: _latest.csv가 없으면 모든 매장이 신규. first_seen_at = 오늘."""
    today = date(2026, 4, 29)
    store = normalize_store(RAW_STORE_BASE)  # open_date = "2008-01-28"
    latest_map = {}  # 빈 맵 = 부트스트랩

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    # 기준 A (OPEN_DATE) = 2008-01, 기준 B (오늘) = 2026-04 → min → 2008/01
    assert month_file == "2008/01", (
        f"부트스트랩 시 등록월은 OPEN_DATE 기준 '2008/01'이어야 한다. 실제: {month_file}"
    )
    assert first_seen_at == "2026-04-29", (
        f"부트스트랩 시 first_seen_at은 오늘({today})이어야 한다. 실제: {first_seen_at}"
    )


# ---------------------------------------------------------------------------
# T06: 신규 매장 등록월 결정 — A < B (오래된 매장 뒤늦게 등장)
# ---------------------------------------------------------------------------


def test_T06_old_store_late_discovery():
    """REQ-EM-004: OPEN_DATE가 오늘보다 오래됐고 _latest에 없으면 OPEN_DATE 월 기준."""
    today = date(2026, 4, 29)
    store = normalize_store(dict(RAW_STORE_BASE, OPEN_DATE="2015.03.15"))
    latest_map = {}  # 처음 발견

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    # A=2015-03, B=2026-04 → min(A,B) → A → "2015/03"
    assert month_file == "2015/03"
    assert first_seen_at == str(today)  # 실제 첫 관측일 = 오늘


# ---------------------------------------------------------------------------
# T07: 신규 매장 등록월 결정 — A > B (예정 오픈 매장)
# ---------------------------------------------------------------------------


def test_T07_future_open_date_store():
    """REQ-EM-004: OPEN_DATE가 오늘보다 미래이면 OPEN_DATE 월 파일에 등록."""
    today = date(2026, 4, 29)
    store = normalize_store(dict(RAW_STORE_BASE, OPEN_DATE="2026.05.25"))
    latest_map = {}

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    # A=2026-05, B=2026-04 → min(A,B)=B이지만 SPEC: 파일은 OPEN_DATE 기준 미래 월
    # SPEC 인수 테스트 #3: 예정 오픈 → "2026/05.csv", first_seen_at = 오늘
    assert month_file == "2026/05"
    assert first_seen_at == str(today)


# ---------------------------------------------------------------------------
# T08: 동일 매장 재실행 시 행 갱신, 월 이동 없음
# ---------------------------------------------------------------------------


def test_T08_existing_store_update_no_month_move():
    """REQ-EM-005: 기존 매장은 current_month_file 보존, first_seen_at 보존, last_seen_at 갱신."""
    today = date(2026, 5, 6)
    store = normalize_store(RAW_STORE_BASE)  # open_date = 2008-01-28

    # 이전 실행에서 이미 관측된 매장
    existing_row = {
        "code": "00060",
        "current_month_file": "2008/01",
        "first_seen_at": "2026-04-29",
        "last_seen_at": "2026-04-29",
    }
    latest_map = {"00060": existing_row}

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    assert month_file == "2008/01", "기존 매장의 current_month_file은 이동하지 않는다."
    assert first_seen_at == "2026-04-29", "기존 매장의 first_seen_at은 보존된다."


# ---------------------------------------------------------------------------
# T09: _latest.csv 재작성 — code ASC 정렬, 26개 컬럼
# ---------------------------------------------------------------------------


def test_T09_rewrite_latest_csv_sorted_26cols(tmp_path):
    """REQ-EM-005b: _latest.csv는 code ASC 정렬, 26개 컬럼으로 재작성된다."""
    today = "2026-04-29"

    stores = []
    for code, month in [
        ("00200", "2020/01"),
        ("00060", "2008/01"),
        ("00150", "2015/03"),
    ]:
        raw = dict(RAW_STORE_BASE, CODE=code)
        store = normalize_store(raw)
        store["first_seen_at"] = today
        store["last_seen_at"] = today
        store["current_month_file"] = month
        stores.append(store)

    latest_path = tmp_path / "emart24" / "_latest.csv"
    latest_path.parent.mkdir(parents=True)

    rewrite_latest_csv(stores, latest_path)

    # 파일 읽기
    with open(latest_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # 컬럼 수 검증
    # 월별 CSV 26개(code~last_seen_at) + current_month_file 1개 = 27개
    assert len(reader.fieldnames) == 27, (
        f"_latest.csv 컬럼은 27개여야 한다. 실제: {len(reader.fieldnames)}"
    )

    # code ASC 정렬 검증
    codes = [r["code"] for r in rows]
    assert codes == sorted(codes), f"code ASC 정렬이어야 한다. 실제: {codes}"

    # current_month_file 컬럼 존재 검증
    assert "current_month_file" in reader.fieldnames


# ---------------------------------------------------------------------------
# T10: API 미관측 매장 — _latest.csv에 보존
# ---------------------------------------------------------------------------


def test_T10_unobserved_store_preserved_in_latest(tmp_path):
    """REQ-EM-005b: 이번 실행에서 API에 없는 매장도 _latest.csv에 보존된다."""
    today = date(2026, 5, 6)
    base_dir = tmp_path / "emart24"
    base_dir.mkdir()

    # 이전 실행: 매장 A, B 있었음
    dict(RAW_STORE_BASE, CODE="00060")
    dict(RAW_STORE_BASE, CODE="00100", TITLE="사라진점")

    # latest_map: 두 매장 모두 기존
    latest_map = {
        "00060": {
            "code": "00060",
            "title": "테스트점",
            "address": "서울시",
            "address_detail": "",
            "phone": "02-1234",
            "lat": "37.5",
            "lng": "127.0",
            "open_date": "2008-01-28",
            "end_date": "",
            "start_hhmm": "00:00",
            "end_hhmm": "00:00",
            "is_24h": "1",
            "svc_parcel": "1",
            "svc_atm": "0",
            "svc_wine": "0",
            "svc_coffee": "1",
            "svc_smoothie": "0",
            "svc_apple": "0",
            "svc_toto": "0",
            "svc_auto": "0",
            "svc_pickup": "1",
            "svc_chicken": "0",
            "svc_noodle": "0",
            "tobacco_license": "1",
            "first_seen_at": "2026-04-29",
            "last_seen_at": "2026-04-29",
            "current_month_file": "2008/01",
        },
        "00100": {
            "code": "00100",
            "title": "사라진점",
            "address": "서울시",
            "address_detail": "",
            "phone": "02-9999",
            "lat": "37.6",
            "lng": "127.1",
            "open_date": "2020-01-01",
            "end_date": "",
            "start_hhmm": "09:00",
            "end_hhmm": "22:00",
            "is_24h": "0",
            "svc_parcel": "0",
            "svc_atm": "0",
            "svc_wine": "0",
            "svc_coffee": "0",
            "svc_smoothie": "0",
            "svc_apple": "0",
            "svc_toto": "0",
            "svc_auto": "0",
            "svc_pickup": "0",
            "svc_chicken": "0",
            "svc_noodle": "0",
            "tobacco_license": "0",
            "first_seen_at": "2026-04-29",
            "last_seen_at": "2026-04-29",
            "current_month_file": "2020/01",
        },
    }

    # 이번 실행: API에서 00060만 관측 (00100 미관측)
    observed_stores = [normalize_store(dict(RAW_STORE_BASE, CODE="00060"))]
    for s in observed_stores:
        s["first_seen_at"] = "2026-04-29"
        s["last_seen_at"] = str(today)
        s["current_month_file"] = "2008/01"

    # update_monthly_csvs 결과 반영 후 _latest.csv 재작성 시뮬레이션
    # 미관측 매장은 latest_map에서 그대로 유지 (last_seen_at 이전 값)
    all_rows = observed_stores + [latest_map["00100"]]

    latest_path = base_dir / "_latest.csv"
    rewrite_latest_csv(all_rows, latest_path)

    with open(latest_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    codes = [r["code"] for r in rows]
    assert "00100" in codes, "미관측 매장 '00100'이 _latest.csv에 보존되어야 한다."

    # 미관측 매장의 last_seen_at은 직전 값(2026-04-29) 유지
    row_100 = next(r for r in rows if r["code"] == "00100")
    assert row_100["last_seen_at"] == "2026-04-29", (
        "미관측 매장의 last_seen_at은 이전 값(2026-04-29)이어야 한다."
    )


# ---------------------------------------------------------------------------
# T11: 트랜잭션 롤백 — 월별 CSV 작성 실패 시 tmp 정리
# ---------------------------------------------------------------------------


def test_T11_transaction_rollback_on_failure(tmp_path):
    """REQ-EM-010: 월별 CSV 작성 실패 시 _latest.csv.tmp가 남지 않는다."""
    base_dir = tmp_path / "emart24"
    base_dir.mkdir()
    latest_path = base_dir / "_latest.csv"
    tmp_path_file = base_dir / "_latest.csv.tmp"

    today = date(2026, 4, 29)
    store = normalize_store(RAW_STORE_BASE)
    store["first_seen_at"] = str(today)
    store["last_seen_at"] = str(today)
    store["current_month_file"] = "2008/01"

    # 쓰기 실패를 유발하는 mock: update_monthly_csvs가 예외를 던짐
    with patch(
        "fetch_emart24.update_monthly_csvs", side_effect=IOError("디스크 쓰기 실패")
    ):
        with patch("fetch_emart24.rewrite_latest_csv"):
            # main() 또는 트랜잭션 함수가 예외 시 tmp 파일을 정리하는지 검증
            # 직접 트랜잭션 함수를 호출하여 롤백 로직 테스트
            from fetch_emart24 import run_transaction

            result = run_transaction(
                api_stores=[store],
                latest_map={},
                base_dir=base_dir,
                today=today,
            )

    # 실패 시 tmp 파일이 남아있지 않아야 한다
    assert not tmp_path_file.exists(), "_latest.csv.tmp가 실패 후 정리되어야 한다."
    # 실패 시 _latest.csv도 생성되지 않아야 한다
    assert not latest_path.exists(), "실패 시 _latest.csv가 생성되지 않아야 한다."
    # 반환값은 None 또는 실패를 나타내는 값이어야 한다
    assert result is None, "트랜잭션 실패 시 None을 반환해야 한다."
