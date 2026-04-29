"""
SPEC-GS25-001: update_changelog_gs25.py 단위 테스트

git diff 파싱, 다이제스트 항목 생성, CHANGELOG prepend 동작을 검증한다.
실제 git 호출 없이 diff 출력 문자열로 직접 테스트한다.
update_changelog.py 테스트와 동일한 패턴을 따르되 gs25 경로를 검증한다.
"""

import sys
from pathlib import Path

# scripts 디렉터리를 import path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from update_changelog_gs25 import (  # noqa: E402
    _month_summary,
    build_digest_entry,
    parse_diff,
    prepend_to_changelog,
)


# 테스트용 헬퍼: 31 컬럼 CSV row 문자열 생성 (gs25 스키마)
def _make_gs25_row(
    code: str,
    title: str,
    last_seen: str,
    month_file: str = "2026/04",
) -> str:
    """31컬럼 gs25 _latest.csv row를 csv 형식 문자열로 만든다."""
    # MONTHLY_COLUMNS(30) + current_month_file(1) = 31개
    # code, title, address, lat, lng, services, svc_*22, first_seen_at, last_seen_at, current_month_file
    svc_zeros = ["0"] * 22
    cols = [
        code,  # code
        title,  # title
        "서울 강남구",  # address
        "37.4792",  # lat
        "127.0453",  # lng
        "atm;cafe25",  # services
        *svc_zeros,  # svc_* 22개
        "2026-04-29",  # first_seen_at
        last_seen,  # last_seen_at
        month_file,  # current_month_file
    ]
    return ",".join(f'"{c}"' for c in cols)


# ---------------------------------------------------------------------------
# T01: 신규 매장 감지
# ---------------------------------------------------------------------------


def test_T01_parse_diff_detects_new_store():
    """완전 신규 매장 (added만 있음)을 신규로 분류한다."""
    diff = [
        "diff --git a/convenience/gs25/_latest.csv b/convenience/gs25/_latest.csv",
        "+++ b/convenience/gs25/_latest.csv",
        "@@ -1,1 +1,2 @@",
        "+" + _make_gs25_row("VQ670", "GS25강남개포점", "2026-04-29"),
    ]
    result = parse_diff(diff, "2026-04-29")
    assert len(result["new"]) == 1
    assert result["new"][0]["code"] == "VQ670"
    assert result["new"][0]["title"] == "GS25강남개포점"
    assert result["updated"] == 0
    assert result["unobserved"] == []


# ---------------------------------------------------------------------------
# T02: 갱신 매장 감지
# ---------------------------------------------------------------------------


def test_T02_parse_diff_detects_update_when_last_seen_today():
    """동일 code가 - 와 + 양쪽에 있고 last_seen_at이 오늘이면 갱신."""
    today = "2026-04-29"
    diff = [
        "+++ b/convenience/gs25/_latest.csv",
        "-" + _make_gs25_row("VQ670", "GS25강남개포점", "2026-04-22"),
        "+" + _make_gs25_row("VQ670", "GS25강남개포점(서비스변경)", today),
    ]
    result = parse_diff(diff, today)
    assert result["new"] == []
    assert result["updated"] == 1
    assert result["unobserved"] == []


# ---------------------------------------------------------------------------
# T03: 미관측 매장 감지
# ---------------------------------------------------------------------------


def test_T03_parse_diff_detects_unobserved_when_last_seen_not_today():
    """동일 code가 양쪽에 있는데 last_seen_at이 오늘이 아니면 미관측."""
    diff = [
        "+++ b/convenience/gs25/_latest.csv",
        "-" + _make_gs25_row("VQ670", "GS25강남개포점", "2026-04-22"),
        "+" + _make_gs25_row("VQ670", "GS25강남개포점", "2026-04-22"),
    ]
    result = parse_diff(diff, "2026-04-29")
    assert result["new"] == []
    assert result["updated"] == 0
    assert len(result["unobserved"]) == 1
    assert result["unobserved"][0]["code"] == "VQ670"


# ---------------------------------------------------------------------------
# T04: 빈 diff
# ---------------------------------------------------------------------------


def test_T04_parse_diff_empty_input_returns_zero_stats():
    """빈 diff는 모든 카운트 0."""
    result = parse_diff([], "2026-04-29")
    assert result["new"] == []
    assert result["updated"] == 0
    assert result["unobserved"] == []


# ---------------------------------------------------------------------------
# T05: 월별 분포 요약
# ---------------------------------------------------------------------------


def test_T05_month_summary_groups_new_by_month():
    """신규 매장의 월별 분포가 정렬된 형태로 요약된다."""
    new_stores = [
        {"month_file": "2026/04"},
        {"month_file": "2026/05"},
        {"month_file": "2026/04"},
        {"month_file": "2026/05"},
        {"month_file": "2026/05"},
    ]
    summary = _month_summary(new_stores)
    assert summary == "2026/04 +2, 2026/05 +3"


# ---------------------------------------------------------------------------
# T06: 다이제스트 항목 생성 — gs25 체인명 확인
# ---------------------------------------------------------------------------


def test_T06_build_digest_entry_includes_gs25_sections():
    """다이제스트 항목이 신규/갱신/미관측 섹션을 모두 포함하고 gs25 관련 URL을 사용한다."""
    stats = {
        "new": [
            {"code": "VQ670", "title": "GS25강남개포점", "month_file": "2026/04"},
            {"code": "AB001", "title": "GS25테스트점", "month_file": "2026/05"},
        ],
        "updated": 5,
        "unobserved": [{"code": "ZZ999", "title": "GS25폐점점"}],
    }
    entry = build_digest_entry(stats, "2026-04-29", "12345", "itda-skills/data-retail")

    assert "## 2026-04-29 (주간 갱신)" in entry
    assert "신규 등록: 2개" in entry
    assert "2026/04 +1" in entry
    assert "2026/05 +1" in entry
    assert "GS25강남개포점" in entry
    assert "GS25테스트점" in entry
    assert "정보 갱신: 5개 매장" in entry
    assert "API 미관측: 1개 매장" in entry
    assert "https://github.com/itda-skills/data-retail/actions/runs/12345" in entry


# ---------------------------------------------------------------------------
# T07: 모두 0인 경우 — 정상 출력
# ---------------------------------------------------------------------------


def test_T07_build_digest_entry_no_changes():
    """모두 0인 경우에도 정상 출력되어야 한다."""
    stats = {"new": [], "updated": 0, "unobserved": []}
    entry = build_digest_entry(stats, "2026-04-29", "", "")
    assert "신규 등록: 0개" in entry
    assert "정보 갱신: 0개 매장" in entry
    assert "API 미관측: 0개" in entry
    assert "수동 실행" in entry


# ---------------------------------------------------------------------------
# T08: 신규 매장 이름 10개 제한
# ---------------------------------------------------------------------------


def test_T08_build_digest_entry_truncates_long_store_names():
    """신규 매장이 11개 이상이면 10개까지만 나열하고 '외 N개'로 요약."""
    new_stores = [
        {"code": f"GS{i:04d}", "title": f"GS25점포{i}", "month_file": "2026/04"}
        for i in range(15)
    ]
    stats = {"new": new_stores, "updated": 0, "unobserved": []}
    entry = build_digest_entry(stats, "2026-04-29", "", "")

    assert "신규 등록: 15개" in entry
    assert "외 5개" in entry
    name_line = [line for line in entry.splitlines() if "신규 매장:" in line][0]
    listed_names = name_line.split(":", 1)[1].split("외")[0]
    assert listed_names.count(",") == 9  # 10개 → 콤마 9개


# ---------------------------------------------------------------------------
# T09: CHANGELOG 신규 생성 — gs25 헤더 확인
# ---------------------------------------------------------------------------


def test_T09_prepend_to_changelog_creates_new_file_with_gs25_header(tmp_path: Path):
    """CHANGELOG.md가 없으면 gs25 헤더와 함께 새로 생성한다."""
    changelog = tmp_path / "CHANGELOG.md"
    entry = "## 2026-04-29 (주간 갱신)\n\n- 신규 등록: 1개\n"

    prepend_to_changelog(entry, changelog)

    content = changelog.read_text(encoding="utf-8")
    # gs25 CHANGELOG 헤더 확인
    assert "gs25" in content.lower() or "GS25" in content, (
        "CHANGELOG 헤더에 gs25가 포함되어야 한다."
    )
    assert "## 2026-04-29 (주간 갱신)" in content


# ---------------------------------------------------------------------------
# T10: CHANGELOG 기존 파일에 역순 삽입
# ---------------------------------------------------------------------------


def test_T10_prepend_to_changelog_inserts_after_header(tmp_path: Path):
    """기존 CHANGELOG가 있으면 헤더 직후에 새 항목을 삽입한다 (역순 시간 정렬)."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# GS25 CHANGELOG\n\n## 2026-04-22 (주간 갱신)\n\n- 이전 항목\n",
        encoding="utf-8",
    )
    new_entry = "## 2026-04-29 (주간 갱신)\n\n- 새 항목\n"

    prepend_to_changelog(new_entry, changelog)

    content = changelog.read_text(encoding="utf-8")
    new_pos = content.index("새 항목")
    old_pos = content.index("이전 항목")
    assert new_pos < old_pos
    assert content.count("# GS25 CHANGELOG") == 1
