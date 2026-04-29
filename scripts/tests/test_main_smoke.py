"""
SPEC-EMART24-001: fetch_emart24.main() 통합 스모크 테스트

실제 API 호출 없이 mocked HTTP 응답으로 main() 전체 흐름을 검증한다.
- _latest.csv 생성/내용 확인
- 월별 CSV 디렉터리 생성
- code zero-pad 보존
- 부트스트랩 (latest_map 비어 있는 상태) 동작
"""

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import fetch_emart24  # noqa: E402


def _make_api_page(stores: list, count: int) -> dict:
    """페이지네이션 응답 형태를 모방한다 (count = 총 매장 수)."""
    return {"count": count, "list": stores}


def _make_raw_store(code: str, title: str, open_date: str = "2020.05.10") -> dict:
    """API 원본 응답 한 매장."""
    return {
        "CODE": code,
        "TITLE": title,
        "ADDRESS": "서울시 어딘가",
        "ADDRESS_DE": "",
        "TEL": "010-1234-5678",
        "LATITUDE": "37.5",
        "LONGITUDE": "127.0",
        "OPEN_DATE": open_date,
        "END_DATE": "9999.12.31",
        "START_HHMM": "0700",
        "END_HHMM": "2300",
        "SVR_24": 0,
        "SVR_PARCEL": 1,
        "SVR_ATM": 0,
        "SVR_WINE": 1,
        "SVR_COFFEE": 1,
        "SVR_SMOOTHIE": 0,
        "SVR_APPLE": 0,
        "SVR_TOTO": 0,
        "SVR_AUTO": 0,
        "SVR_PICKUP": 0,
        "SVR_CHICKEN": 0,
        "SVR_NOODLE": 0,
        "BUSINESS_LICENSE": 1,
    }


@pytest.fixture
def fake_session():
    """requests.Session 을 흉내내는 mock 세션. get() 호출에 페이지별 응답."""
    session = MagicMock()

    page1 = _make_api_page(
        [
            _make_raw_store("00060", "동대사랑점", "2008.01.28"),
            _make_raw_store("12345", "강남2호점", "2020.05.10"),
        ],
        count=3,
    )
    page2 = _make_api_page(
        [_make_raw_store("99999", "예정오픈점", "2026.05.25")],
        count=3,
    )

    responses = [page1, page2]
    call_count = {"n": 0}

    def fake_get(url, params=None, headers=None, timeout=None):
        idx = call_count["n"]
        call_count["n"] += 1
        resp = MagicMock()
        if idx < len(responses):
            resp.status_code = 200
            resp.json.return_value = responses[idx]
        else:
            resp.status_code = 200
            resp.json.return_value = {"count": 3, "list": []}
        resp.raise_for_status = MagicMock()
        return resp

    session.get = MagicMock(side_effect=fake_get)
    return session


def test_main_bootstrap_creates_latest_and_monthly(tmp_path, monkeypatch, fake_session):
    """첫 실행 (부트스트랩): _latest.csv 와 월별 CSV 가 생성되고 내용이 일관되어야 한다."""
    base_dir = tmp_path / "emart24"

    # PAGE_SIZE 를 작게 해서 두 번째 페이지로 넘어가게 한다 (실제 카운트와 매칭)
    monkeypatch.setattr(fetch_emart24, "PAGE_SIZE", 2)
    # delay 0 으로 강제하여 테스트 빠르게
    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_emart24.py", "--delay", "0", "--base-dir", str(base_dir)],
    )

    with patch.object(fetch_emart24, "requests") as mock_requests:
        mock_requests.Session.return_value = fake_session
        exit_code = fetch_emart24.main()

    assert exit_code == 0

    latest_path = base_dir / "_latest.csv"
    assert latest_path.exists(), "_latest.csv 가 생성되어야 한다"

    with latest_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    # code 가 zero-pad 5자리로 보존되는지
    codes = sorted(r["code"] for r in rows)
    assert codes == ["00060", "12345", "99999"]
    # ASC 정렬 확인
    assert [r["code"] for r in rows] == ["00060", "12345", "99999"]
    # 27 컬럼 확인
    assert len(rows[0]) == 27
    # current_month_file 정확성
    code_to_mf = {r["code"]: r["current_month_file"] for r in rows}
    assert code_to_mf["00060"] == "2008/01"
    assert code_to_mf["12345"] == "2020/05"
    assert code_to_mf["99999"] == "2026/05"  # 예정 오픈도 OPEN_DATE 월에 등록

    # 월별 CSV 도 생성되어야 한다
    assert (base_dir / "2008" / "01.csv").exists()
    assert (base_dir / "2020" / "05.csv").exists()
    assert (base_dir / "2026" / "05.csv").exists()


def test_main_returns_1_on_duplicate_code(tmp_path, monkeypatch):
    """같은 실행 내에 중복 code 가 발견되면 exit 1."""
    base_dir = tmp_path / "emart24"

    dup_session = MagicMock()
    dup_resp = MagicMock()
    dup_resp.status_code = 200
    dup_resp.json.return_value = _make_api_page(
        [
            _make_raw_store("00060", "A점"),
            _make_raw_store("00060", "B점"),  # 의도적 중복
        ],
        count=2,
    )
    dup_resp.raise_for_status = MagicMock()
    dup_session.get = MagicMock(return_value=dup_resp)

    monkeypatch.setattr(
        sys,
        "argv",
        ["fetch_emart24.py", "--delay", "0", "--base-dir", str(base_dir)],
    )

    with patch.object(fetch_emart24, "requests") as mock_requests:
        mock_requests.Session.return_value = dup_session
        exit_code = fetch_emart24.main()

    assert exit_code == 1


def test_cli_help_runs_without_error():
    """--help 가 정상 종료한다 (argparse 정의 sanity)."""
    with pytest.raises(SystemExit) as exc:
        with patch.object(sys, "argv", ["fetch_emart24.py", "--help"]):
            fetch_emart24.main()
    assert exc.value.code == 0
