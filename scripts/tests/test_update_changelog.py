"""
SPEC-EMART24-001: update_changelog.py 단위 테스트

git diff 파싱, 다이제스트 항목 생성, CHANGELOG prepend 동작을 검증한다.
실제 git 호출 없이 diff 출력 문자열로 직접 테스트한다.
"""

import sys
from pathlib import Path

# scripts 디렉터리를 import path 에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from update_changelog import (  # noqa: E402
    _month_summary,
    build_digest_entry,
    parse_diff,
    prepend_to_changelog,
)


# 테스트용 헬퍼: 27 컬럼 CSV row 문자열 생성
def _make_row(
    code: str,
    title: str,
    last_seen: str,
    month_file: str = "2026/04",
    open_date: str = "2026-04-01",
) -> str:
    """27컬럼 _latest.csv row 를 csv 형식 문자열로 만든다."""
    cols = [
        code,
        title,
        "주소",
        "",
        "010-1234-5678",
        "37.5",
        "127.0",
        open_date,
        "",
        "06:00",
        "00:00",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "2026-04-01",
        last_seen,
        month_file,
    ]
    return ",".join(f'"{c}"' for c in cols)


def test_parse_diff_detects_new_store():
    """완전 신규 매장 (added 만 있음) 을 신규로 분류한다."""
    diff = [
        "diff --git a/emart24/_latest.csv b/emart24/_latest.csv",
        "+++ b/emart24/_latest.csv",
        "@@ -1,1 +1,2 @@",
        "+" + _make_row("00100", "강남신규점", "2026-04-29"),
    ]
    result = parse_diff(diff, "2026-04-29")
    assert len(result["new"]) == 1
    assert result["new"][0]["code"] == "00100"
    assert result["new"][0]["title"] == "강남신규점"
    assert result["updated"] == 0
    assert result["unobserved"] == []


def test_parse_diff_detects_update_when_last_seen_today():
    """동일 code 가 - 와 + 양쪽에 있고 last_seen_at 이 오늘이면 갱신."""
    today = "2026-04-29"
    diff = [
        "+++ b/emart24/_latest.csv",
        "-" + _make_row("00060", "동대사랑점", "2026-04-22"),
        "+" + _make_row("00060", "동대사랑점-개명", today),
    ]
    result = parse_diff(diff, today)
    assert result["new"] == []
    assert result["updated"] == 1
    assert result["unobserved"] == []


def test_parse_diff_detects_unobserved_when_last_seen_not_today():
    """동일 code 가 양쪽에 있는데 last_seen_at 이 오늘이 아니면 미관측."""
    diff = [
        "+++ b/emart24/_latest.csv",
        "-" + _make_row("00200", "구로점", "2026-04-22"),
        "+" + _make_row("00200", "구로점", "2026-04-22"),
    ]
    result = parse_diff(diff, "2026-04-29")
    assert result["new"] == []
    assert result["updated"] == 0
    assert len(result["unobserved"]) == 1
    assert result["unobserved"][0]["code"] == "00200"


def test_parse_diff_empty_input_returns_zero_stats():
    """빈 diff 는 모든 카운트 0."""
    result = parse_diff([], "2026-04-29")
    assert result["new"] == []
    assert result["updated"] == 0
    assert result["unobserved"] == []


def test_month_summary_groups_new_by_month():
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


def test_build_digest_entry_includes_all_sections():
    """다이제스트 항목이 신규/갱신/미관측 섹션을 모두 포함한다."""
    stats = {
        "new": [
            {"code": "00100", "title": "신규A", "month_file": "2026/04"},
            {"code": "00101", "title": "신규B", "month_file": "2026/05"},
        ],
        "updated": 5,
        "unobserved": [{"code": "00999", "title": "사라진점"}],
    }
    entry = build_digest_entry(stats, "2026-04-29", "12345", "itda-skills/data-retail")

    assert "## 2026-04-29 (주간 갱신)" in entry
    assert "신규 등록: 2개" in entry
    assert "2026/04 +1" in entry
    assert "2026/05 +1" in entry
    assert "신규A" in entry
    assert "신규B" in entry
    assert "정보 갱신: 5개 매장" in entry
    assert "API 미관측: 1개 매장" in entry
    assert "https://github.com/itda-skills/data-retail/actions/runs/12345" in entry


def test_build_digest_entry_no_changes():
    """모두 0인 경우에도 정상 출력되어야 한다."""
    stats = {"new": [], "updated": 0, "unobserved": []}
    entry = build_digest_entry(stats, "2026-04-29", "", "")
    assert "신규 등록: 0개" in entry
    assert "정보 갱신: 0개 매장" in entry
    assert "API 미관측: 0개" in entry
    assert "수동 실행" in entry  # run_id 없으면 fallback


def test_build_digest_entry_truncates_long_store_names():
    """신규 매장이 11개 이상이면 10개까지만 나열하고 '외 N개' 로 요약."""
    new_stores = [
        {"code": f"0010{i}", "title": f"매장{i}", "month_file": "2026/04"}
        for i in range(15)
    ]
    stats = {"new": new_stores, "updated": 0, "unobserved": []}
    entry = build_digest_entry(stats, "2026-04-29", "", "")

    assert "신규 등록: 15개" in entry
    assert "외 5개" in entry
    # 0~9 만 표시되고 10~14 는 표시되지 않아야 함
    assert "매장9" in entry
    # 첫 10개 매장명만 노출 (정확히 검증)
    name_line = [line for line in entry.splitlines() if "신규 매장:" in line][0]
    listed_names = name_line.split(":", 1)[1].split("외")[0]
    assert listed_names.count(",") == 9  # 10개 → 콤마 9개


def test_prepend_to_changelog_creates_new_file(tmp_path: Path):
    """CHANGELOG.md 가 없으면 헤더와 함께 새로 생성한다."""
    changelog = tmp_path / "CHANGELOG.md"
    entry = "## 2026-04-29 (주간 갱신)\n\n- 신규 등록: 1개\n"

    prepend_to_changelog(entry, changelog)

    content = changelog.read_text(encoding="utf-8")
    assert content.startswith("# emart24 CHANGELOG\n\n")
    assert "## 2026-04-29 (주간 갱신)" in content


def test_prepend_to_changelog_inserts_after_header(tmp_path: Path):
    """기존 CHANGELOG 가 있으면 헤더 직후에 새 항목을 삽입한다 (역순 시간 정렬)."""
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# emart24 CHANGELOG\n\n## 2026-04-22 (주간 갱신)\n\n- 이전 항목\n",
        encoding="utf-8",
    )
    new_entry = "## 2026-04-29 (주간 갱신)\n\n- 새 항목\n"

    prepend_to_changelog(new_entry, changelog)

    content = changelog.read_text(encoding="utf-8")
    # 새 항목이 이전 항목보다 위에 와야 함
    new_pos = content.index("새 항목")
    old_pos = content.index("이전 항목")
    assert new_pos < old_pos
    # 헤더는 한 번만 존재
    assert content.count("# emart24 CHANGELOG") == 1
