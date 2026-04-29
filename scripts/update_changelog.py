"""
SPEC-EMART24-001: 주간 변경 다이제스트 생성 스크립트
git diff HEAD~1 -- emart24/_latest.csv 를 분석하여 CHANGELOG.md에 항목을 추가한다.
"""
import os
import subprocess
import sys
from datetime import date
from pathlib import Path


# CHANGELOG 항목 최대 매장명 수 (초과 시 "외 N개")
MAX_STORE_NAMES = 10


def get_diff_lines(repo_root: Path) -> list:
    """
    git diff HEAD~1 -- emart24/_latest.csv 결과를 줄 단위로 반환한다.
    HEAD~1이 없으면 (첫 커밋) 빈 리스트를 반환한다.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--", "emart24/_latest.csv"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError:
        return []


def parse_diff(diff_lines: list, today_str: str) -> dict:
    """
    diff 출력에서 신규/갱신/미관측 매장을 분류한다.

    Args:
        diff_lines: git diff 출력 줄 목록
        today_str: 오늘 날짜 문자열 (YYYY-MM-DD)

    Returns:
        {
          new: [{code, title, month_file}],
          updated: int,
          unobserved: [{code, title}],
        }
    """
    added_rows = []    # '+' 로 시작하는 데이터 행
    removed_rows = []  # '-' 로 시작하는 데이터 행

    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            added_rows.append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            removed_rows.append(line[1:])

    # 추가된 code 집합
    added_codes: dict = {}  # code → row
    for row in added_rows:
        parts = _split_csv_row(row)
        if len(parts) >= 27 and parts[0].strip('"') not in ("code",):
            code = parts[0].strip('"')
            title = parts[1].strip('"') if len(parts) > 1 else ""
            month_file = parts[-1].strip('"') if parts else ""
            last_seen = parts[25].strip('"') if len(parts) > 25 else ""
            added_codes[code] = {
                "code": code, "title": title,
                "month_file": month_file, "last_seen_at": last_seen,
            }

    # 제거된 code 집합
    removed_codes: set = set()
    removed_map: dict = {}
    for row in removed_rows:
        parts = _split_csv_row(row)
        if len(parts) >= 1:
            code = parts[0].strip('"')
            if code and code != "code":
                removed_codes.add(code)
                title = parts[1].strip('"') if len(parts) > 1 else ""
                removed_map[code] = {"code": code, "title": title}

    new_stores = []
    updated_count = 0
    unobserved_stores = []

    for code, info in added_codes.items():
        if code not in removed_codes:
            # 완전 신규 (이전에 없던 code)
            new_stores.append(info)
        else:
            # 기존 행 변경
            if info.get("last_seen_at") == today_str:
                updated_count += 1
            else:
                unobserved_stores.append(removed_map.get(code, {"code": code, "title": ""}))

    # removed_codes에 있지만 added_codes에 없는 것 = 완전 사라진 행 (미관측)
    for code in removed_codes:
        if code not in added_codes:
            unobserved_stores.append(removed_map.get(code, {"code": code, "title": ""}))

    return {
        "new": new_stores,
        "updated": updated_count,
        "unobserved": unobserved_stores,
    }


def _split_csv_row(row: str) -> list:
    """간단한 CSV 행 분리 (따옴표 처리)."""
    import csv
    reader = csv.reader([row])
    try:
        return next(reader)
    except StopIteration:
        return []


def _month_summary(new_stores: list) -> str:
    """신규 매장의 월별 분포 요약 문자열을 생성한다 (예: '2026/04 +5, 2026/05 +7')."""
    month_count: dict = {}
    for store in new_stores:
        mf = store.get("month_file", "?")
        month_count[mf] = month_count.get(mf, 0) + 1

    parts = [f"{mf} +{cnt}" for mf, cnt in sorted(month_count.items())]
    return ", ".join(parts)


def build_digest_entry(stats: dict, today_str: str, run_id: str, repository: str) -> str:
    """
    CHANGELOG.md에 추가할 다이제스트 항목 문자열을 생성한다.

    Args:
        stats: parse_diff() 결과
        today_str: 오늘 날짜 (YYYY-MM-DD)
        run_id: GITHUB_RUN_ID
        repository: GITHUB_REPOSITORY

    Returns:
        CHANGELOG 항목 문자열
    """
    new_stores = stats["new"]
    updated_count = stats["updated"]
    unobserved = stats["unobserved"]

    new_count = len(new_stores)
    unobserved_count = len(unobserved)

    lines = [f"## {today_str} (주간 갱신)", ""]

    if new_count > 0:
        month_summary = _month_summary(new_stores)
        lines.append(f"- 신규 등록: {new_count}개 ({month_summary})")
        # 매장명 최대 MAX_STORE_NAMES개
        names = [s["title"] for s in new_stores if s.get("title")][:MAX_STORE_NAMES]
        remaining = new_count - len(names)
        names_str = ", ".join(names)
        if remaining > 0:
            names_str += f" 외 {remaining}개"
        if names_str:
            lines.append(f"  - 신규 매장: {names_str}")
    else:
        lines.append("- 신규 등록: 0개")

    lines.append(f"- 정보 갱신: {updated_count}개 매장")

    if unobserved_count > 0:
        lines.append(f"- API 미관측: {unobserved_count}개 매장 — 폐점/이전 가능성")
    else:
        lines.append("- API 미관측: 0개")

    lines.append("")

    if run_id and repository:
        run_url = f"https://github.com/{repository}/actions/runs/{run_id}"
        lines.append(f"실행: [{run_id}]({run_url})")
    else:
        lines.append("실행: 수동 실행")

    return "\n".join(lines) + "\n"


def prepend_to_changelog(entry: str, changelog_path: Path) -> None:
    """
    CHANGELOG.md 파일 맨 앞에 항목을 추가한다.
    파일이 없으면 새로 생성한다.
    """
    header = "# emart24 CHANGELOG\n\n"

    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        # 헤더 다음에 삽입
        if existing.startswith(header):
            new_content = header + entry + "\n" + existing[len(header):]
        else:
            new_content = existing + "\n" + entry
    else:
        new_content = header + entry

    changelog_path.write_text(new_content, encoding="utf-8")


def main() -> int:
    """다이제스트 생성 메인 함수."""
    repo_root = Path(__file__).parent.parent
    changelog_path = repo_root / "emart24" / "CHANGELOG.md"
    today_str = str(date.today())
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")

    diff_lines = get_diff_lines(repo_root)

    if not diff_lines:
        print("[정보] 변경 없음. CHANGELOG 갱신 건너뜀.")
        return 0

    stats = parse_diff(diff_lines, today_str)
    entry = build_digest_entry(stats, today_str, run_id, repository)
    prepend_to_changelog(entry, changelog_path)

    print(
        f"[완료] CHANGELOG 갱신: 신규={len(stats['new'])}, "
        f"갱신={stats['updated']}, 미관측={len(stats['unobserved'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
