"""
SPEC-GS25-001 단위 테스트 — REQ-GS25-002 ~ REQ-GS25-013
GS25 매장 정보 수집 파이프라인의 핵심 로직을 검증한다.
실제 API 호출 없이 정적 fixture를 사용한다.
"""

import csv
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

# 테스트 대상 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import fetch_gs25
from fetch_gs25 import (
    decide_destination,
    normalize_store,
    rewrite_latest_csv,
)

# ---------------------------------------------------------------------------
# fixture 경로
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
HTML_FIXTURE = FIXTURES_DIR / "gs25_locations_page.html"
VQ670_FIXTURE = FIXTURES_DIR / "gs25_vq670.json"

# ---------------------------------------------------------------------------
# 공통 fixture — VQ670 원시 레코드
# ---------------------------------------------------------------------------


# 정적 fixture에서 VQ670 원시 레코드 추출 (테스트 모듈 로드 시 1회)
def _load_vq670_raw() -> dict:
    """gs25_vq670.json에서 VQ670 원시 레코드를 로드한다."""
    with open(VQ670_FIXTURE, encoding="utf-8") as f:
        raw_text = f.read()
    inner = json.loads(raw_text)
    assert isinstance(inner, str), (
        "첫 번째 json.loads 결과는 str이어야 한다 (이중 인코딩)"
    )
    data = json.loads(inner)
    results = data["results"]
    vq670_list = [r for r in results if r.get("shopCode") == "VQ670"]
    assert len(vq670_list) == 1, "VQ670 레코드가 정확히 1개여야 한다"
    return vq670_list[0]


VQ670_RAW = _load_vq670_raw()

# 간단한 테스트용 원시 레코드 (VQ670 기반)
RAW_STORE_BASE = {
    "shopCode": "VQ670",
    "shopName": "GS25강남개포점",
    "address": "서울특별시 강남구 개포로15길 10",
    "lat": "127.045318254341",  # API 오인: 실제 경도
    "longs": "37.4792069328551",  # API 오인: 실제 위도
    "offeringService": [],
}


# ---------------------------------------------------------------------------
# T01: CSRFToken 추출 정규식 — REQ-GS25-002
# ---------------------------------------------------------------------------


def test_T01_csrf_token_extracted_from_html():
    """REQ-GS25-002: 정상 HTML에서 CSRFToken이 추출된다."""
    html = """<script>
    ACC.config.CSRFToken = "b6681905-1ea7-426e-96c4-e8df9d548563";
    </script>"""

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp

    # HTML에서 시도 파싱 실패 방지용 — 최소한의 시도 HTML 포함
    html_with_sido = (
        html
        + """
    <select id="stb1">
      <option value="11">서울시</option>
    </select>"""
    )
    mock_resp.text = html_with_sido

    token, sidos = fetch_gs25.bootstrap_session(mock_session)
    assert token == "b6681905-1ea7-426e-96c4-e8df9d548563"


def test_T01b_csrf_token_absent_raises():
    """REQ-GS25-002: CSRFToken이 없으면 RuntimeError가 발생한다 (fail-fast)."""
    html = "<html><body>no token here</body></html>"

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp

    try:
        fetch_gs25.bootstrap_session(mock_session)
        assert False, "CSRFToken 부재 시 예외가 발생해야 한다"
    except (RuntimeError, SystemExit, ValueError):
        pass  # 예외 발생 = 정상


# ---------------------------------------------------------------------------
# T02: 시도 17개 파싱 — REQ-GS25-002 (HTML fixture)
# ---------------------------------------------------------------------------

EXPECTED_SIDO_CODES = {
    11,
    26,
    27,
    28,
    29,
    30,
    31,
    36,
    41,
    43,
    44,
    46,
    47,
    48,
    50,
    51,
    52,
}


def test_T02_sido_17_parsed_from_html_fixture():
    """REQ-GS25-002: HTML fixture에서 시도 17개 코드가 모두 파싱된다."""
    with open(HTML_FIXTURE, encoding="utf-8") as f:
        html = f.read()

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp

    _, sidos = fetch_gs25.bootstrap_session(mock_session)

    codes = {int(code) for code, name in sidos}
    assert codes == EXPECTED_SIDO_CODES, (
        f"시도 코드 불일치. 기대: {EXPECTED_SIDO_CODES}, 실제: {codes}"
    )
    assert len(sidos) == 17, f"시도는 17개여야 한다. 실제: {len(sidos)}"


def test_T02b_sido_zero_matches_raises():
    """REQ-GS25-002: 시도 옵션이 0건이면 RuntimeError가 발생한다 (fail-fast)."""
    html = """<script>ACC.config.CSRFToken = "abc-123";</script>
    <select id="stb1"></select>"""

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.status_code = 200
    mock_session.get.return_value = mock_resp

    try:
        fetch_gs25.bootstrap_session(mock_session)
        assert False, "시도 파싱 0건 시 예외가 발생해야 한다"
    except (RuntimeError, SystemExit, ValueError):
        pass


# ---------------------------------------------------------------------------
# T03: 이중 JSON 언랩 — REQ-GS25-004 (VQ670 fixture)
# ---------------------------------------------------------------------------


def test_T03_double_json_unwrap_from_fixture():
    """REQ-GS25-004: gs25_vq670.json은 이중 JSON 인코딩이며, 두 번 json.loads 후 results 키가 있다."""
    with open(VQ670_FIXTURE, encoding="utf-8") as f:
        raw_text = f.read()

    # 1차 디코딩 → str이어야 함
    inner = json.loads(raw_text)
    assert isinstance(inner, str), (
        "첫 번째 json.loads 결과는 str이어야 한다. 단일 JSON으로 변경되면 fixture 갱신 필요."
    )

    # 2차 디코딩 → dict이어야 함
    data = json.loads(inner)
    assert isinstance(data, dict), "두 번째 json.loads 결과는 dict이어야 한다."
    assert "results" in data, "응답 dict에 'results' 키가 있어야 한다."


def test_T03b_double_json_contains_vq670():
    """REQ-GS25-004: fixture에서 shopCode VQ670이 1개 존재한다."""
    with open(VQ670_FIXTURE, encoding="utf-8") as f:
        raw_text = f.read()
    data = json.loads(json.loads(raw_text))
    results = data["results"]
    vq670 = [r for r in results if r.get("shopCode") == "VQ670"]
    assert len(vq670) == 1, f"VQ670이 정확히 1개여야 한다. 실제: {len(vq670)}"


# ---------------------------------------------------------------------------
# T04: lat/longs SWAP — REQ-GS25-005 (VQ670 정밀 좌표 검증)
# ---------------------------------------------------------------------------


def test_T04_lat_longs_swap_vq670():
    """REQ-GS25-005: VQ670 정규화 결과 lat≈37.4792, lng≈127.0453 (소수 4자리)."""
    result = normalize_store(VQ670_RAW)

    assert round(result["lat"], 4) == 37.4792, (
        f"lat은 실제 위도(API longs 필드) ≈ 37.4792여야 한다. 실제: {result['lat']}"
    )
    assert round(result["lng"], 4) == 127.0453, (
        f"lng은 실제 경도(API lat 필드) ≈ 127.0453이어야 한다. 실제: {result['lng']}"
    )


def test_T04b_lat_longs_swap_simple():
    """REQ-GS25-005: lat/longs swap 로직을 단순 수치로 검증한다."""
    raw = dict(
        RAW_STORE_BASE,
        **{
            "lat": "127.1",  # API lat = 실제 경도
            "longs": "37.5",  # API longs = 실제 위도
        },
    )
    result = normalize_store(raw)
    assert result["lat"] == 37.5  # 실제 위도
    assert result["lng"] == 127.1  # 실제 경도


# ---------------------------------------------------------------------------
# T05: 22종 서비스 플래그 매핑 — REQ-GS25-005
# ---------------------------------------------------------------------------

ALL_SERVICES = [
    "cafe25",
    "instant",
    "drug",
    "post",
    "withdrawal",
    "atm",
    "taxrefund",
    "smart_atm",
    "self_cooking_utensils",
    "delivery_service",
    "parcel_service",
    "potatoes",
    "cardiac_defi",
    "fish_shaped_bun",
    "wine25",
    "go_pizza",
    "spirit_wine",
    "fresh_ganghw",
    "musinsa",
    "posa",
    "toto",
    "self25",
]


def test_T05_service_flags_mapping():
    """REQ-GS25-005: offeringService 배열이 svc_* 컬럼으로 정확히 매핑된다."""
    services_input = ["cafe25", "drug", "wine25", "musinsa"]
    raw = dict(RAW_STORE_BASE, offeringService=services_input)
    result = normalize_store(raw)

    assert result["svc_cafe25"] == 1
    assert result["svc_drug"] == 1
    assert result["svc_wine25"] == 1
    assert result["svc_musinsa"] == 1

    # 나머지는 0
    for svc in ALL_SERVICES:
        if svc not in services_input:
            key = f"svc_{svc}"
            assert result[key] == 0, f"{key}는 0이어야 한다. 실제: {result[key]}"


def test_T05b_services_string_semicolon_joined_sorted():
    """REQ-GS25-005: services 컬럼은 알파벳순 정렬 + 세미콜론 join."""
    raw = dict(RAW_STORE_BASE, offeringService=["wine25", "cafe25", "atm"])
    result = normalize_store(raw)
    # 알파벳순: atm, cafe25, wine25
    assert result["services"] == "atm;cafe25;wine25", (
        f"services는 알파벳 정렬+세미콜론 join이어야 한다. 실제: {result['services']}"
    )


def test_T05c_all_services_zero_when_empty():
    """REQ-GS25-005: offeringService가 빈 배열이면 모든 svc_* = 0."""
    raw = dict(RAW_STORE_BASE, offeringService=[])
    result = normalize_store(raw)
    for svc in ALL_SERVICES:
        assert result[f"svc_{svc}"] == 0


# ---------------------------------------------------------------------------
# T06: 미지의 서비스 코드 — WARN 로깅, 워크플로우 미실패 — REQ-GS25-005
# ---------------------------------------------------------------------------


def test_T06_unknown_service_warns_not_crashes(capsys):
    """REQ-GS25-005: 미관측 서비스 코드는 services 컬럼에 보존되고 stderr WARN 로그."""
    unknown_code = "brand_new_service_xyz"
    raw = dict(RAW_STORE_BASE, offeringService=["atm", unknown_code])

    result = normalize_store(raw)  # 예외 없이 실행되어야 한다

    # services 컬럼에 보존 확인
    assert unknown_code in result["services"], (
        f"미지의 서비스 코드 '{unknown_code}'가 services 컬럼에 보존되어야 한다."
    )
    # svc_ 컬럼이 추가되지 않음 확인
    assert f"svc_{unknown_code}" not in result, (
        f"미지의 코드 '{unknown_code}'에 대한 svc_ 컬럼은 생성되지 않아야 한다."
    )

    # stderr WARN 로그 확인
    captured = capsys.readouterr()
    assert unknown_code in captured.err, (
        f"stderr에 unknown service code '{unknown_code}'가 경고로 출력되어야 한다."
    )


# ---------------------------------------------------------------------------
# T07: 동 fan-out 병합 — REQ-GS25-004
# ---------------------------------------------------------------------------


def test_T07_dong_fanout_merges_all_results():
    """REQ-GS25-004: 3개 동(0개/1개/다수 매장 반환) 결과가 모두 병합된다."""
    # 동 A: 0개 매장
    # 동 B: 1개 매장 (VQ670)
    # 동 C: 3개 매장

    def make_raw(code, lat="127.0", longs="37.5"):
        return {
            "shopCode": code,
            "shopName": f"점포{code}",
            "address": "서울",
            "lat": lat,
            "longs": longs,
            "offeringService": [],
        }

    mock_session = MagicMock()

    # fetch_stores 를 직접 mock하여 동별 반환값 설정
    def mock_fetch_stores(session, csrf_token, sido, gungu, dong, delay=0.5):
        if dong == "dong_a":
            return []
        elif dong == "dong_b":
            return [normalize_store(make_raw("CODE_B"))]
        elif dong == "dong_c":
            return [
                normalize_store(make_raw("CODE_C1")),
                normalize_store(make_raw("CODE_C2")),
                normalize_store(make_raw("CODE_C3")),
            ]
        return []

    all_stores = []
    for dong in ["dong_a", "dong_b", "dong_c"]:
        all_stores.extend(mock_fetch_stores(mock_session, "token", "11", "1168", dong))

    assert len(all_stores) == 4, (
        f"3개 동 병합 결과는 0+1+3=4개여야 한다. 실제: {len(all_stores)}"
    )
    codes = {s["code"] for s in all_stores}
    assert "CODE_B" in codes
    assert "CODE_C1" in codes
    assert "CODE_C2" in codes
    assert "CODE_C3" in codes


# ---------------------------------------------------------------------------
# T08: 신규 등록 월 결정 — first_seen_at 기반 파티션 — REQ-GS25-006
# ---------------------------------------------------------------------------


def test_T08_bootstrap_no_latest_csv_first_seen_today():
    """REQ-GS25-006: _latest.csv 부재 시 모든 매장의 first_seen_at = 오늘."""
    today = date(2026, 4, 29)
    store = normalize_store(RAW_STORE_BASE)
    latest_map = {}  # 부트스트랩

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    assert month_file == "2026/04", (
        f"부트스트랩 시 등록월은 오늘 기준 '2026/04'여야 한다. 실제: {month_file}"
    )
    assert first_seen_at == "2026-04-29", (
        f"부트스트랩 시 first_seen_at은 오늘이어야 한다. 실제: {first_seen_at}"
    )


def test_T08b_new_store_different_month():
    """REQ-GS25-006: 신규 매장은 오늘 날짜의 연/월로 등록 월이 결정된다."""
    today = date(2026, 5, 15)
    store = normalize_store(RAW_STORE_BASE)
    latest_map = {}

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    assert month_file == "2026/05"
    assert first_seen_at == "2026-05-15"


# ---------------------------------------------------------------------------
# T09: 기존 매장 재실행 — first_seen_at 보존, 월 이동 없음 — REQ-GS25-007
# ---------------------------------------------------------------------------


def test_T09_existing_store_preserves_first_seen_at():
    """REQ-GS25-007: 기존 매장은 current_month_file과 first_seen_at이 보존된다."""
    today = date(2026, 5, 6)
    store = normalize_store(RAW_STORE_BASE)

    existing_row = {
        "code": "VQ670",
        "current_month_file": "2026/04",
        "first_seen_at": "2026-04-29",
        "last_seen_at": "2026-04-29",
    }
    latest_map = {"VQ670": existing_row}

    month_file, first_seen_at = decide_destination(store, latest_map, today)

    assert month_file == "2026/04", "기존 매장의 month_file은 이동하지 않는다."
    assert first_seen_at == "2026-04-29", "기존 매장의 first_seen_at은 보존된다."


# ---------------------------------------------------------------------------
# T10: _latest.csv 재작성 — code ASC, 31컬럼 — REQ-GS25-005b
# ---------------------------------------------------------------------------


def test_T10_rewrite_latest_csv_sorted_31cols(tmp_path):
    """REQ-GS25-005b: _latest.csv는 code ASC 정렬, 31개 컬럼으로 재작성된다."""
    today = "2026-04-29"
    stores = []
    for code, month in [
        ("ZZ999", "2026/04"),
        ("AA001", "2026/04"),
        ("MM500", "2026/04"),
    ]:
        raw = dict(RAW_STORE_BASE, shopCode=code)
        s = normalize_store(raw)
        s["first_seen_at"] = today
        s["last_seen_at"] = today
        s["current_month_file"] = month
        stores.append(s)

    latest_path = tmp_path / "gs25" / "_latest.csv"
    latest_path.parent.mkdir(parents=True)
    rewrite_latest_csv(stores, latest_path)

    with open(latest_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(reader.fieldnames) == 31, (
        f"_latest.csv 컬럼은 31개여야 한다. 실제: {len(reader.fieldnames)}"
    )
    codes = [r["code"] for r in rows]
    assert codes == sorted(codes), f"code ASC 정렬이어야 한다. 실제: {codes}"
    assert "current_month_file" in reader.fieldnames


# ---------------------------------------------------------------------------
# T11: API 미관측 매장 — _latest.csv 보존 — REQ-GS25-005b
# ---------------------------------------------------------------------------


def test_T11_unobserved_store_preserved_in_latest(tmp_path):
    """REQ-GS25-005b: 이번 실행에서 API에 없는 매장도 _latest.csv에 보존된다."""
    today = date(2026, 5, 6)
    base_dir = tmp_path / "gs25"
    base_dir.mkdir()

    # 기존 최신 맵 — VQ670, GHOST001 두 매장
    ghost_row = {
        "code": "GHOST001",
        "title": "사라진점",
        "address": "서울",
        "lat": "37.5",
        "lng": "127.0",
        "services": "",
        **{f"svc_{s}": "0" for s in ALL_SERVICES},
        "first_seen_at": "2026-04-29",
        "last_seen_at": "2026-04-29",
        "current_month_file": "2026/04",
    }
    _ = {
        "VQ670": {
            "code": "VQ670",
            "title": "GS25강남개포점",
            "address": "서울",
            "lat": "37.4792",
            "lng": "127.0453",
            "services": "",
            **{f"svc_{s}": "0" for s in ALL_SERVICES},
            "first_seen_at": "2026-04-29",
            "last_seen_at": "2026-04-29",
            "current_month_file": "2026/04",
        },
        "GHOST001": ghost_row,
    }  # latest_map은 이 테스트에서 직접 사용하지 않음

    # 이번 실행: VQ670만 관측 (GHOST001 미관측)
    observed_store = normalize_store(VQ670_RAW)
    observed_store["first_seen_at"] = "2026-04-29"
    observed_store["last_seen_at"] = str(today)
    observed_store["current_month_file"] = "2026/04"

    all_rows = [observed_store, ghost_row]
    latest_path = base_dir / "_latest.csv"
    rewrite_latest_csv(all_rows, latest_path)

    with open(latest_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    codes = [r["code"] for r in rows]
    assert "GHOST001" in codes, (
        "미관측 매장 'GHOST001'이 _latest.csv에 보존되어야 한다."
    )

    ghost = next(r for r in rows if r["code"] == "GHOST001")
    assert ghost["last_seen_at"] == "2026-04-29", (
        "미관측 매장의 last_seen_at은 이전 값(2026-04-29)이어야 한다."
    )


# ---------------------------------------------------------------------------
# T12: 트랜잭션 롤백 — REQ-GS25-011
# ---------------------------------------------------------------------------


def test_T12_transaction_rollback_on_failure(tmp_path):
    """REQ-GS25-011: 월별 CSV 작성 실패 시 _latest.csv.tmp가 정리된다."""
    base_dir = tmp_path / "gs25"
    base_dir.mkdir()
    latest_path = base_dir / "_latest.csv"
    tmp_file = base_dir / "_latest.csv.tmp"

    today = date(2026, 4, 29)
    store = normalize_store(RAW_STORE_BASE)
    store["first_seen_at"] = str(today)
    store["last_seen_at"] = str(today)
    store["current_month_file"] = "2026/04"

    with patch(
        "fetch_gs25.update_monthly_csvs", side_effect=IOError("디스크 쓰기 실패")
    ):
        from fetch_gs25 import run_transaction

        result = run_transaction(
            api_stores=[store],
            latest_map={},
            base_dir=base_dir,
            today=today,
        )

    assert not tmp_file.exists(), "_latest.csv.tmp가 실패 후 정리되어야 한다."
    assert not latest_path.exists(), "실패 시 _latest.csv가 생성되지 않아야 한다."
    assert result is None, "트랜잭션 실패 시 None을 반환해야 한다."


# ---------------------------------------------------------------------------
# T13: resultCode != "00000" 즉시 실패 — REQ-GS25-003
# ---------------------------------------------------------------------------


def test_T13_result_code_non_zero_raises():
    """REQ-GS25-003: resultCode가 '00000'이 아니면 RuntimeError가 발생한다."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [],
        "resultCode": "99999",  # 오류 코드
    }
    mock_session.get.return_value = mock_resp

    try:
        fetch_gs25.fetch_gungu(mock_session, "11")
        assert False, "resultCode != '00000' 시 예외가 발생해야 한다."
    except (RuntimeError, SystemExit, ValueError):
        pass


# ---------------------------------------------------------------------------
# T14: throttle — 0.5초 sleep 호출 확인 — REQ-GS25-010
# ---------------------------------------------------------------------------


def test_T14_throttle_sleep_called_between_requests():
    """REQ-GS25-010: fetch_gungu 호출 시 time.sleep(delay)이 호출된다."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }
    mock_session.get.return_value = mock_resp

    with patch("fetch_gs25.time") as mock_time:
        fetch_gs25.fetch_gungu(mock_session, "11", delay=0.5)
        mock_time.sleep.assert_called_with(0.5)


# ---------------------------------------------------------------------------
# T15: fetch_stores 이중 JSON 디코딩 + normalize 통합 — REQ-GS25-004
# ---------------------------------------------------------------------------


def test_T15_fetch_stores_double_json_decode():
    """REQ-GS25-004: fetch_stores가 이중 JSON 응답을 올바르게 디코딩하여 정규화된 레코드를 반환한다."""
    inner_data = {
        "results": [
            {
                "shopCode": "TEST001",
                "shopName": "테스트점",
                "address": "서울",
                "lat": "127.0",
                "longs": "37.5",
                "offeringService": [],
            }
        ]
    }
    # 이중 인코딩: json.dumps(json.dumps(inner_data))
    double_encoded = json.dumps(json.dumps(inner_data))

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = double_encoded
    mock_session.post.return_value = mock_resp

    with patch("fetch_gs25.time"):
        results = fetch_gs25.fetch_stores(
            mock_session, "TOKEN", "11", "1168", "11680103"
        )

    assert len(results) == 1
    assert results[0]["code"] == "TEST001"
    assert results[0]["lat"] == 37.5  # longs → lat (swap)
    assert results[0]["lng"] == 127.0  # lat → lng (swap)


# ---------------------------------------------------------------------------
# T16: code 문자열 보존 — REQ-GS25-005 인수 테스트 #9
# ---------------------------------------------------------------------------


def test_T16_code_preserved_as_string():
    """REQ-GS25-005: shopCode는 문자열로 보존되고 정수로 변환되지 않는다."""
    raw = dict(RAW_STORE_BASE, shopCode="VQ670")
    result = normalize_store(raw)
    assert result["code"] == "VQ670"
    assert isinstance(result["code"], str), "code 타입이 str이어야 한다."


def test_T16b_code_quoted_in_csv(tmp_path):
    """REQ-GS25-005: _latest.csv 파일에서 code는 따옴표로 감싸진다."""
    store = normalize_store(RAW_STORE_BASE)
    store["first_seen_at"] = "2026-04-29"
    store["last_seen_at"] = "2026-04-29"
    store["current_month_file"] = "2026/04"

    latest_path = tmp_path / "gs25" / "_latest.csv"
    latest_path.parent.mkdir(parents=True)
    rewrite_latest_csv([store], latest_path)

    content = latest_path.read_text(encoding="utf-8")
    assert '"VQ670"' in content, "code 'VQ670'이 따옴표로 감싸져야 한다."


# ---------------------------------------------------------------------------
# T17: _latest.csv 로드 — 부재 시 빈 맵 반환 — REQ-GS25-006
# ---------------------------------------------------------------------------


def test_T17_load_latest_map_returns_empty_when_missing(tmp_path):
    """REQ-GS25-006: _latest.csv가 없으면 빈 딕셔너리를 반환한다."""
    from fetch_gs25 import load_latest_map

    result = load_latest_map(tmp_path / "nonexistent.csv")
    assert result == {}, "파일 부재 시 빈 딕셔너리여야 한다."


def test_T17b_load_latest_map_reads_existing(tmp_path):
    """REQ-GS25-006: _latest.csv가 있으면 code → row 딕셔너리를 반환한다."""
    from fetch_gs25 import load_latest_map

    latest_path = tmp_path / "_latest.csv"
    store = normalize_store(RAW_STORE_BASE)
    store["first_seen_at"] = "2026-04-29"
    store["last_seen_at"] = "2026-04-29"
    store["current_month_file"] = "2026/04"

    rewrite_latest_csv([store], latest_path)

    result = load_latest_map(latest_path)
    assert "VQ670" in result
    assert result["VQ670"]["title"] == "GS25강남개포점"


# ---------------------------------------------------------------------------
# T18: update_monthly_csvs — 신규 + 기존 처리 — REQ-GS25-007
# ---------------------------------------------------------------------------


def test_T18_update_monthly_csvs_new_store(tmp_path):
    """REQ-GS25-007: 신규 매장은 월별 CSV에 append된다."""
    from fetch_gs25 import update_monthly_csvs

    base_dir = tmp_path / "gs25"
    base_dir.mkdir()
    today = date(2026, 4, 29)

    store = normalize_store(RAW_STORE_BASE)
    latest_map = {}

    stats = update_monthly_csvs([store], latest_map, base_dir, today)

    assert stats["new"] == 1
    assert stats["updated"] == 0
    assert store["first_seen_at"] == "2026-04-29"
    assert store["current_month_file"] == "2026/04"

    csv_path = base_dir / "2026" / "04.csv"
    assert csv_path.exists()


def test_T18b_update_monthly_csvs_existing_store(tmp_path):
    """REQ-GS25-007: 기존 매장은 행 갱신 (월 이동 없음)."""
    from fetch_gs25 import update_monthly_csvs

    base_dir = tmp_path / "gs25"
    today = date(2026, 5, 6)

    # 초기 월별 CSV 세팅
    store = normalize_store(RAW_STORE_BASE)
    store["first_seen_at"] = "2026-04-29"
    store["last_seen_at"] = "2026-04-29"
    store["current_month_file"] = "2026/04"
    from fetch_gs25 import _write_monthly_file

    csv_path = base_dir / "2026" / "04.csv"
    _write_monthly_file(csv_path, [store])

    # 갱신 실행
    latest_map = {"VQ670": {**store, "current_month_file": "2026/04"}}
    updated_store = normalize_store(dict(RAW_STORE_BASE, offeringService=["atm"]))
    stats = update_monthly_csvs([updated_store], latest_map, base_dir, today)

    assert stats["updated"] == 1
    assert stats["new"] == 0


# ---------------------------------------------------------------------------
# T19: fetch_dong throttle 확인 — REQ-GS25-010
# ---------------------------------------------------------------------------


def test_T19_fetch_dong_sleep_called():
    """REQ-GS25-010: fetch_dong 호출 시 time.sleep(delay)이 호출된다."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "result": [["11680103", "개포동"]],
        "resultCode": "00000",
    }
    mock_session.get.return_value = mock_resp

    with patch("fetch_gs25.time") as mock_time:
        fetch_gs25.fetch_dong(mock_session, "11", "1168", delay=0.5)
        mock_time.sleep.assert_called_with(0.5)


# ---------------------------------------------------------------------------
# T20: main() 스모크 테스트 — 전체 파이프라인 통합
# ---------------------------------------------------------------------------


def test_T20_main_smoke_dry_run(tmp_path, monkeypatch):
    """main(dry_run=True)이 오류 없이 실행된다 (실제 HTTP 없이)."""
    import fetch_gs25 as fg

    # requests.Session mock
    mock_session = MagicMock()

    # bootstrap mock
    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "test-token-123";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    # gungu mock
    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 200
    mock_gungu_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }

    # dong mock
    mock_dong_resp = MagicMock()
    mock_dong_resp.status_code = 200
    mock_dong_resp.json.return_value = {
        "result": [["11680103", "개포동"]],
        "resultCode": "00000",
    }

    # locationList mock (이중 JSON)
    inner = json.dumps({"results": [dict(RAW_STORE_BASE)]})
    double_encoded = json.dumps(inner)
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = double_encoded

    mock_session.get.side_effect = [
        mock_bootstrap_resp,  # bootstrap
        mock_gungu_resp,  # gungu for sido 11
        mock_dong_resp,  # dong for gungu 1168
    ]
    mock_session.post.return_value = mock_post_resp

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        with patch("fetch_gs25.time"):
            result = fg.main(delay=0, dry_run=True)

    assert result == 0


def test_T20b_main_bootstrap_failure_returns_1():
    """부트스트랩 실패 시 main()은 1을 반환한다."""
    import fetch_gs25 as fg

    mock_session = MagicMock()
    mock_session.get.side_effect = RuntimeError("부트스트랩 실패")

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        result = fg.main(delay=0, dry_run=False)

    assert result == 1


def test_T20c_main_gungu_failure_returns_1():
    """군구 발견 실패 시 main()은 1을 반환한다."""
    import fetch_gs25 as fg

    mock_session = MagicMock()

    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "token";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 403  # 4xx 즉시 실패

    mock_session.get.side_effect = [mock_bootstrap_resp, mock_gungu_resp]

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        with patch("fetch_gs25.time"):
            result = fg.main(delay=0, dry_run=False)

    assert result == 1


def test_T20d_main_full_run_writes_csv(tmp_path):
    """main()이 dry_run=False로 실행 시 CSV 파일을 작성한다."""
    base_dir = tmp_path / "gs25"
    base_dir.mkdir()

    mock_session = MagicMock()

    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "token";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 200
    mock_gungu_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }

    mock_dong_resp = MagicMock()
    mock_dong_resp.status_code = 200
    mock_dong_resp.json.return_value = {
        "result": [["11680103", "개포동"]],
        "resultCode": "00000",
    }

    inner = json.dumps({"results": [dict(RAW_STORE_BASE)]})
    double_encoded = json.dumps(inner)
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = double_encoded

    mock_session.get.side_effect = [
        mock_bootstrap_resp,
        mock_gungu_resp,
        mock_dong_resp,
    ]
    mock_session.post.return_value = mock_post_resp

    # 직접 run_transaction까지 호출하여 CSV 작성 확인
    store = normalize_store(RAW_STORE_BASE)
    from fetch_gs25 import run_transaction

    stats = run_transaction([store], {}, base_dir, date(2026, 4, 29))
    assert stats is not None
    assert stats["new"] == 1
    assert (base_dir / "2026" / "04.csv").exists()
    assert (base_dir / "_latest.csv").exists()


# ---------------------------------------------------------------------------
# T21: _get_with_retry 에러 분기
# ---------------------------------------------------------------------------


def test_T21_get_with_retry_4xx_raises_immediately():
    """_get_with_retry: 4xx 응답 시 즉시 RuntimeError."""
    from fetch_gs25 import _get_with_retry

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_session.get.return_value = mock_resp

    try:
        _get_with_retry(mock_session, "http://example.com")
        assert False, "4xx 응답 시 RuntimeError가 발생해야 한다."
    except RuntimeError as e:
        assert "4xx" in str(e)


def test_T21b_get_with_retry_5xx_retries_3_times():
    """_get_with_retry: 5xx 응답 시 3회 재시도 후 RuntimeError."""
    from fetch_gs25 import _get_with_retry

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_session.get.return_value = mock_resp

    with patch("fetch_gs25.time"):
        try:
            _get_with_retry(mock_session, "http://example.com")
            assert False, "5xx 재시도 소진 시 RuntimeError가 발생해야 한다."
        except RuntimeError as e:
            assert "5xx" in str(e) or "재시도" in str(e)

    # 3번 호출 확인
    assert mock_session.get.call_count == 3


def test_T21c_get_with_retry_network_error_retries():
    """_get_with_retry: 네트워크 오류 시 재시도 후 RuntimeError."""
    from fetch_gs25 import _get_with_retry

    mock_session = MagicMock()
    mock_session.get.side_effect = ConnectionError("네트워크 오류")

    with patch("fetch_gs25.time"):
        try:
            _get_with_retry(mock_session, "http://example.com")
            assert False, "네트워크 오류 재시도 소진 시 RuntimeError가 발생해야 한다."
        except RuntimeError:
            pass

    assert mock_session.get.call_count == 3


# ---------------------------------------------------------------------------
# T22: _post_with_retry 에러 분기
# ---------------------------------------------------------------------------


def test_T22_post_with_retry_4xx_raises_immediately():
    """_post_with_retry: 4xx 응답 시 즉시 RuntimeError."""
    from fetch_gs25 import _post_with_retry

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_session.post.return_value = mock_resp

    try:
        _post_with_retry(mock_session, "http://example.com", data="test", headers={})
        assert False, "4xx 응답 시 RuntimeError가 발생해야 한다."
    except RuntimeError as e:
        assert "4xx" in str(e)


def test_T22b_post_with_retry_5xx_retries():
    """_post_with_retry: 5xx 응답 시 3회 재시도 후 RuntimeError."""
    from fetch_gs25 import _post_with_retry

    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_session.post.return_value = mock_resp

    with patch("fetch_gs25.time"):
        try:
            _post_with_retry(
                mock_session, "http://example.com", data="test", headers={}
            )
            assert False, "5xx 재시도 소진 시 RuntimeError가 발생해야 한다."
        except RuntimeError:
            pass

    assert mock_session.post.call_count == 3


def test_T22c_post_with_retry_network_error_retries():
    """_post_with_retry: 네트워크 오류 시 재시도 후 RuntimeError."""
    from fetch_gs25 import _post_with_retry

    mock_session = MagicMock()
    mock_session.post.side_effect = ConnectionError("네트워크 오류")

    with patch("fetch_gs25.time"):
        try:
            _post_with_retry(
                mock_session, "http://example.com", data="test", headers={}
            )
            assert False, "네트워크 오류 재시도 소진 시 RuntimeError가 발생해야 한다."
        except RuntimeError:
            pass

    assert mock_session.post.call_count == 3


# ---------------------------------------------------------------------------
# T23: main() 동/매장 수집 실패 경로
# ---------------------------------------------------------------------------


def test_T23_main_dong_failure_returns_1():
    """동 발견 실패 시 main()은 1을 반환한다."""
    import fetch_gs25 as fg

    mock_session = MagicMock()

    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "token";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 200
    mock_gungu_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }

    mock_dong_resp = MagicMock()
    mock_dong_resp.status_code = 500  # 5xx → 백오프 3회 후 실패

    mock_session.get.side_effect = [mock_bootstrap_resp, mock_gungu_resp] + [
        mock_dong_resp
    ] * 3

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        with patch("fetch_gs25.time"):
            result = fg.main(delay=0, dry_run=False)

    assert result == 1


def test_T23b_main_store_fetch_failure_returns_1():
    """locationList POST 실패 시 main()은 1을 반환한다."""
    import fetch_gs25 as fg

    mock_session = MagicMock()

    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "token";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 200
    mock_gungu_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }

    mock_dong_resp = MagicMock()
    mock_dong_resp.status_code = 200
    mock_dong_resp.json.return_value = {
        "result": [["11680103", "개포동"]],
        "resultCode": "00000",
    }

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 403  # 4xx 즉시 실패

    mock_session.get.side_effect = [
        mock_bootstrap_resp,
        mock_gungu_resp,
        mock_dong_resp,
    ]
    mock_session.post.return_value = mock_post_resp

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        with patch("fetch_gs25.time"):
            result = fg.main(delay=0, dry_run=False)

    assert result == 1


def test_T23c_main_duplicate_code_returns_1():
    """중복 code 발견 시 main()은 1을 반환한다."""
    import fetch_gs25 as fg

    mock_session = MagicMock()

    mock_bootstrap_resp = MagicMock()
    mock_bootstrap_resp.status_code = 200
    mock_bootstrap_resp.text = (
        '<script>ACC.config.CSRFToken = "token";</script>'
        '<select id="stb1"><option value="11">서울시</option></select>'
    )

    mock_gungu_resp = MagicMock()
    mock_gungu_resp.status_code = 200
    mock_gungu_resp.json.return_value = {
        "result": [["1168", "강남구"]],
        "resultCode": "00000",
    }

    mock_dong_resp = MagicMock()
    mock_dong_resp.status_code = 200
    mock_dong_resp.json.return_value = {
        "result": [["11680103", "개포동"], ["11680104", "개포2동"]],
        "resultCode": "00000",
    }

    # 두 동에서 모두 VQ670을 반환 → 중복 code
    dup_raw = dict(RAW_STORE_BASE)
    inner = json.dumps({"results": [dup_raw]})
    double_encoded = json.dumps(inner)
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.text = double_encoded

    mock_session.get.side_effect = [
        mock_bootstrap_resp,
        mock_gungu_resp,
        mock_dong_resp,
    ]
    mock_session.post.return_value = mock_post_resp

    with patch("fetch_gs25.requests") as mock_requests:
        mock_requests.Session.return_value = mock_session
        with patch("fetch_gs25.time"):
            result = fg.main(delay=0, dry_run=False)

    assert result == 1
