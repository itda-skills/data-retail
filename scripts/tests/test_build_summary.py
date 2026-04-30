"""build_summary.py 테스트.

체인 무관 동작 검증 + 출력 스키마 검증 + 폐점 후보 필터 정확성 검증.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import build_summary  # noqa: E402


# emart24 스타일 컬럼 (open_date 보유)
EMART24_HEADER = [
    "code",
    "title",
    "address",
    "lat",
    "lng",
    "open_date",
    "first_seen_at",
    "last_seen_at",
]

# gs25 스타일 컬럼 (open_date 없음)
GS25_HEADER = [
    "code",
    "title",
    "address",
    "lat",
    "lng",
    "services",
    "first_seen_at",
    "last_seen_at",
]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def make_emart24_dir(tmp_path: Path) -> Path:
    chain_dir = tmp_path / "emart24"
    chain_dir.mkdir()
    rows = [
        # code, title, address, lat, lng, open_date, first_seen_at, last_seen_at
        [
            "00060",
            "동대사랑점",
            "서울특별시 중구 퇴계로44길 8",
            "37.56",
            "126.99",
            "2008-01-28",
            "2026-04-01",
            "2026-04-29",
        ],
        [
            "00087",
            "중림점",
            "서울특별시 중구 청파로 464",
            "37.56",
            "126.96",
            "2008-02-16",
            "2026-04-01",
            "2026-04-29",
        ],
        [
            "10001",
            "강남점",
            "서울특별시 강남구 테헤란로 100",
            "37.49",
            "127.03",
            "2020-05-10",
            "2026-04-01",
            "2026-04-29",
        ],
        [
            "20001",
            "수원점",
            "경기도 수원시 영통구 광교로 1",
            "37.28",
            "127.04",
            "2018-07-15",
            "2026-04-01",
            "2026-04-29",
        ],
        # 폐점 후보: last_seen_at 이 max - 14일 이상 과거
        [
            "99999",
            "폐점예상점",
            "부산광역시 해운대구 해변로 1",
            "35.16",
            "129.16",
            "2010-03-01",
            "2026-01-01",
            "2026-04-01",
        ],
        # sentinel: open_date 9999 → by_open_year 에 포함되면 안 됨
        [
            "88888",
            "미정점",
            "충청북도 청주시 상당구 미정로 1",
            "36.64",
            "127.49",
            "9999-12-31",
            "2026-04-01",
            "2026-04-29",
        ],
    ]
    write_csv(chain_dir / "_latest.csv", EMART24_HEADER, rows)
    # 월별 파일 일부 생성 → monthly_files 수집 검증
    (chain_dir / "2008").mkdir()
    (chain_dir / "2008" / "01.csv").write_text("code\n00060\n", encoding="utf-8")
    (chain_dir / "2008" / "02.csv").write_text("code\n00087\n", encoding="utf-8")
    (chain_dir / "2020").mkdir()
    (chain_dir / "2020" / "05.csv").write_text("code\n10001\n", encoding="utf-8")
    return chain_dir


def make_gs25_dir(tmp_path: Path) -> Path:
    chain_dir = tmp_path / "gs25"
    chain_dir.mkdir()
    rows = [
        # code, title, address, lat, lng, services, first_seen_at, last_seen_at
        [
            "V1018",
            "GS25잠실구장점",
            "서울 송파구 올림픽로 25",
            "37.51",
            "127.07",
            "cardiac_defi",
            "2026-04-30",
            "2026-04-30",
        ],
        [
            "V1019",
            "GS25잠실1루점",
            "서울 송파구 올림픽로 25",
            "37.52",
            "127.07",
            "",
            "2026-04-30",
            "2026-04-30",
        ],
        [
            "VQ670",
            "GS25부산점",
            "부산 해운대구 우동 100",
            "35.16",
            "129.16",
            "wine25",
            "2026-04-30",
            "2026-04-30",
        ],
    ]
    write_csv(chain_dir / "_latest.csv", GS25_HEADER, rows)
    (chain_dir / "2026").mkdir()
    (chain_dir / "2026" / "04.csv").write_text("code\nV1018\n", encoding="utf-8")
    return chain_dir


# ---------- 단위 테스트 ----------


def test_parse_sido_sigungu():
    assert build_summary.parse_sido_sigungu("서울특별시 중구 퇴계로 1") == (
        "서울특별시",
        "중구",
    )
    assert build_summary.parse_sido_sigungu("서울 송파구 올림픽로 25") == (
        "서울",
        "송파구",
    )
    assert build_summary.parse_sido_sigungu("") == ("", "")
    assert build_summary.parse_sido_sigungu("부산광역시") == ("부산광역시", "")


def test_parse_iso_date():
    from datetime import date

    assert build_summary.parse_iso_date("2026-04-29") == date(2026, 4, 29)
    assert build_summary.parse_iso_date("") is None
    assert build_summary.parse_iso_date("invalid") is None
    assert build_summary.parse_iso_date("9999-12-31") == date(9999, 12, 31)


def test_extract_open_year_filters_sentinel():
    """비현실 미래·sentinel 연도는 by_open_year 에 포함되지 않아야 한다 (AI-GUIDE §4.1)."""
    assert build_summary.extract_open_year({"open_date": "2020-05-10"}) == "2020"
    assert build_summary.extract_open_year({"open_date": "9999-12-31"}) == ""
    assert build_summary.extract_open_year({"open_date": "2100-12-01"}) == ""
    # open_date 없으면 first_seen_at 폴백
    assert (
        build_summary.extract_open_year(
            {"open_date": "", "first_seen_at": "2026-04-30"}
        )
        == "2026"
    )


# ---------- 통합 테스트: emart24 스타일 ----------


def test_build_chain_summary_emart24(tmp_path: Path):
    chain_dir = make_emart24_dir(tmp_path)
    result = build_summary.build_chain_summary(chain_dir)

    # 파일 생성 확인
    assert result["summary_path"].exists()
    assert result["index_path"].exists()
    assert result["closure_path"].exists()

    # summary.json 내용 검증
    summary = json.loads(result["summary_path"].read_text(encoding="utf-8"))
    assert summary["chain"] == "emart24"
    assert summary["total_stores"] == 6
    assert summary["last_seen_at_max"] == "2026-04-29"
    # 시도 카운트 (서울 4, 경기 1, 부산 1, 충북 1)
    assert summary["by_sido"]["서울특별시"] == 3
    assert summary["by_sido"]["경기도"] == 1
    assert summary["by_sido"]["부산광역시"] == 1
    # by_open_year: 9999 sentinel 제외, 2008/2010/2018/2020 만
    assert "9999" not in summary["by_open_year"]
    assert summary["by_open_year"]["2008"] == 2
    assert summary["by_open_year"]["2020"] == 1
    # 월별 파일 수집 (2008/01, 2008/02, 2020/05)
    assert summary["monthly_files"] == ["2008/01.csv", "2008/02.csv", "2020/05.csv"]
    assert summary["closure_threshold_days"] == 14


def test_build_chain_summary_index_columns_emart24(tmp_path: Path):
    chain_dir = make_emart24_dir(tmp_path)
    result = build_summary.build_chain_summary(chain_dir)

    with result["index_path"].open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == build_summary.INDEX_COLUMNS
        rows = list(reader)
    assert len(rows) == 6
    # code zero-pad 보존
    assert rows[0]["code"] == "00060"
    # sido/sigungu 분리
    assert rows[0]["sido"] == "서울특별시"
    assert rows[0]["sigungu"] == "중구"


def test_build_chain_summary_closure_emart24(tmp_path: Path):
    chain_dir = make_emart24_dir(tmp_path)
    result = build_summary.build_chain_summary(chain_dir)

    # 폐점 후보: 99999 한 개 (last_seen_at 2026-04-01, max 2026-04-29, 28일 격차)
    assert result["closure_count"] == 1
    with result["closure_path"].open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["code"] == "99999"
    # 원본 컬럼 보존
    assert "open_date" in reader.fieldnames


# ---------- 통합 테스트: gs25 스타일 (open_date 없음) ----------


def test_build_chain_summary_gs25_without_open_date(tmp_path: Path):
    """gs25 처럼 open_date 컬럼이 없어도 first_seen_at 폴백으로 동작해야 한다."""
    chain_dir = make_gs25_dir(tmp_path)
    result = build_summary.build_chain_summary(chain_dir)

    summary = json.loads(result["summary_path"].read_text(encoding="utf-8"))
    assert summary["chain"] == "gs25"
    assert summary["total_stores"] == 3
    # first_seen_at = 2026-04-30 폴백
    assert summary["by_open_year"]["2026"] == 3
    # 폐점 후보 없음 (모두 동일 last_seen_at)
    assert result["closure_count"] == 0


def test_build_chain_summary_closure_csv_has_header_when_empty(tmp_path: Path):
    """폐점 후보가 0개여도 헤더만 있는 CSV 가 생성되어야 한다."""
    chain_dir = make_gs25_dir(tmp_path)
    result = build_summary.build_chain_summary(chain_dir)

    content = result["closure_path"].read_text(encoding="utf-8")
    lines = content.splitlines()
    assert len(lines) == 1  # 헤더만
    assert lines[0].startswith("code,")


# ---------- 에러 케이스 ----------


def test_missing_latest_csv_raises(tmp_path: Path):
    empty_dir = tmp_path / "empty_chain"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        build_summary.build_chain_summary(empty_dir)


def test_missing_required_columns_raises(tmp_path: Path):
    chain_dir = tmp_path / "broken"
    chain_dir.mkdir()
    write_csv(chain_dir / "_latest.csv", ["code", "title"], [["X1", "이름"]])
    with pytest.raises(ValueError, match="필수 컬럼 누락"):
        build_summary.build_chain_summary(chain_dir)


def test_non_directory_raises(tmp_path: Path):
    bogus = tmp_path / "doesnotexist"
    with pytest.raises(ValueError, match="체인 디렉터리가 아니다"):
        build_summary.build_chain_summary(bogus)


# ---------- CLI 스모크 ----------


def test_main_cli_success(tmp_path: Path, capsys):
    chain_dir = make_emart24_dir(tmp_path)
    rc = build_summary.main(["build_summary.py", str(chain_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[emart24] 보조 파일 생성 완료" in out
    assert "총 매장: 6" in out


def test_main_cli_bad_args(capsys):
    rc = build_summary.main(["build_summary.py"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "사용:" in err


def test_main_cli_missing_dir(tmp_path: Path, capsys):
    rc = build_summary.main(["build_summary.py", str(tmp_path / "nope")])
    assert rc == 1
