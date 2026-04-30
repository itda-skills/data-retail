"""체인 _latest.csv → 보조 요약 파일 3종 생성.

생성 파일:
  - _summary.json: 전체 통계 (총 매장 수, 시도별 카운트, 연도별 등록 추세 등)
  - _index.csv: 매장 검색용 경량 인덱스 (code, title, sido, sigungu, lat, lng, first/last_seen_at)
  - _closure_candidates.csv: last_seen_at 갱신 중단 매장 (폐점 후보)

체인에 무관하게 동작하도록 설계되었다. _latest.csv 의 컬럼이 체인마다
달라도 본 스크립트가 요구하는 최소 컬럼 (code, title, address, lat, lng,
first_seen_at, last_seen_at) 만 있으면 동작한다.

사용:
    python scripts/build_summary.py convenience/emart24
    python scripts/build_summary.py convenience/gs25

자동화 테스트: scripts/tests/test_build_summary.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

# 폐점 후보 임계값: last_seen_at_max 기준 N일 이상 미관측이면 후보
CLOSURE_THRESHOLD_DAYS = 14

# 인덱스 파일 컬럼 (검색·매핑용 경량 셋)
INDEX_COLUMNS = [
    "code",
    "title",
    "sido",
    "sigungu",
    "lat",
    "lng",
    "first_seen_at",
    "last_seen_at",
]

# _latest.csv 가 반드시 가져야 할 최소 컬럼
REQUIRED_COLUMNS = {"code", "title", "address", "first_seen_at", "last_seen_at"}


def parse_sido_sigungu(address: str) -> tuple[str, str]:
    """한국 주소 문자열에서 시도·시군구 토큰을 추출한다.

    체인마다 표기가 다르다 (emart24: '서울특별시 중구 ...', gs25: '서울 송파구 ...').
    원본 토큰을 그대로 보존한다 — 정규화는 하지 않는다.
    """
    if not address:
        return ("", "")
    parts = address.strip().split()
    sido = parts[0] if len(parts) >= 1 else ""
    sigungu = parts[1] if len(parts) >= 2 else ""
    return (sido, sigungu)


def parse_iso_date(s: str) -> date | None:
    """ISO 날짜 문자열 (YYYY-MM-DD) 을 date 로 파싱. 실패 시 None."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def extract_open_year(row: dict) -> str:
    """open_date 가 있으면 연도를, 없으면 first_seen_at 연도를 반환."""
    for key in ("open_date", "first_seen_at"):
        val = row.get(key, "")
        if val and len(val) >= 4 and val[:4].isdigit():
            year = val[:4]
            # 비현실 미래·sentinel 필터 (AI-GUIDE §4.1)
            if "2007" <= year <= "2030":
                return year
    return ""


def collect_monthly_files(chain_dir: Path) -> list[str]:
    """{chain_dir}/{YYYY}/{MM}.csv 파일 목록을 정렬된 상대 경로로 반환."""
    results = []
    for year_dir in sorted(chain_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_csv in sorted(year_dir.glob("*.csv")):
            results.append(f"{year_dir.name}/{month_csv.name}")
    return results


def build_summary(rows: list[dict], chain_name: str, monthly_files: list[str]) -> dict:
    """전체 통계 dict 를 생성한다."""
    last_seen_dates = [
        d for d in (parse_iso_date(r.get("last_seen_at", "")) for r in rows) if d
    ]
    last_seen_max = max(last_seen_dates).isoformat() if last_seen_dates else ""

    by_sido: Counter[str] = Counter()
    by_open_year: Counter[str] = Counter()
    for row in rows:
        sido, _ = parse_sido_sigungu(row.get("address", ""))
        if sido:
            by_sido[sido] += 1
        year = extract_open_year(row)
        if year:
            by_open_year[year] += 1

    return {
        "chain": chain_name,
        "generated_at": date.today().isoformat(),
        "last_seen_at_max": last_seen_max,
        "total_stores": len(rows),
        "by_sido": dict(sorted(by_sido.items(), key=lambda kv: -kv[1])),
        "by_open_year": dict(sorted(by_open_year.items())),
        "monthly_files": monthly_files,
        "closure_threshold_days": CLOSURE_THRESHOLD_DAYS,
    }


def build_index_rows(rows: list[dict]) -> list[list[str]]:
    """인덱스 CSV 의 데이터 행들을 반환 (헤더 제외)."""
    out = []
    for row in rows:
        sido, sigungu = parse_sido_sigungu(row.get("address", ""))
        out.append(
            [
                row.get("code", ""),
                row.get("title", ""),
                sido,
                sigungu,
                row.get("lat", ""),
                row.get("lng", ""),
                row.get("first_seen_at", ""),
                row.get("last_seen_at", ""),
            ]
        )
    return out


def build_closure_candidates(
    rows: list[dict], threshold_days: int = CLOSURE_THRESHOLD_DAYS
) -> tuple[list[dict], list[str]]:
    """폐점 후보 행과 원본 컬럼 순서를 반환한다.

    last_seen_at_max - row.last_seen_at >= threshold_days 인 행이 후보.
    """
    last_seen_dates = [
        d for d in (parse_iso_date(r.get("last_seen_at", "")) for r in rows) if d
    ]
    if not last_seen_dates:
        return ([], list(rows[0].keys()) if rows else [])
    cutoff_max = max(last_seen_dates)
    threshold = cutoff_max - timedelta(days=threshold_days)
    candidates = []
    for row in rows:
        last_seen = parse_iso_date(row.get("last_seen_at", ""))
        if last_seen is None:
            continue
        if last_seen <= threshold:
            candidates.append(row)
    fieldnames = list(rows[0].keys()) if rows else []
    return (candidates, fieldnames)


def read_latest_csv(path: Path) -> list[dict]:
    """_latest.csv 를 읽어 dict 행 리스트로 반환. 컬럼 부족 시 ValueError."""
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: 헤더가 없거나 빈 파일이다")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path}: 필수 컬럼 누락: {sorted(missing)}")
        return list(reader)


def write_summary_json(path: Path, summary: dict) -> None:
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: list[str], rows: list) -> None:
    """CSV 작성 (RFC 4180, LF 개행). rows 는 dict 또는 list 모두 허용."""
    with path.open("w", encoding="utf-8", newline="") as f:
        if rows and isinstance(rows[0], dict):
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        else:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(fieldnames)
            writer.writerows(rows)


def build_chain_summary(chain_dir: Path) -> dict:
    """체인 디렉터리에 대해 3종 보조 파일을 생성한다.

    반환: 생성된 파일 경로와 요약 메타데이터를 담은 dict (테스트용).
    """
    if not chain_dir.is_dir():
        raise ValueError(f"체인 디렉터리가 아니다: {chain_dir}")

    latest_path = chain_dir / "_latest.csv"
    if not latest_path.exists():
        raise FileNotFoundError(f"_latest.csv 가 없다: {latest_path}")

    rows = read_latest_csv(latest_path)
    chain_name = chain_dir.name
    monthly_files = collect_monthly_files(chain_dir)

    # 1) summary.json
    summary = build_summary(rows, chain_name, monthly_files)
    summary_path = chain_dir / "_summary.json"
    write_summary_json(summary_path, summary)

    # 2) index.csv
    index_rows = build_index_rows(rows)
    index_path = chain_dir / "_index.csv"
    write_csv(index_path, INDEX_COLUMNS, index_rows)

    # 3) closure_candidates.csv
    candidates, fieldnames = build_closure_candidates(rows)
    closure_path = chain_dir / "_closure_candidates.csv"
    write_csv(closure_path, fieldnames or INDEX_COLUMNS, candidates)

    return {
        "summary_path": summary_path,
        "index_path": index_path,
        "closure_path": closure_path,
        "summary": summary,
        "index_count": len(index_rows),
        "closure_count": len(candidates),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("사용: python build_summary.py <chain_dir>", file=sys.stderr)
        print("예: python build_summary.py convenience/emart24", file=sys.stderr)
        return 2

    chain_dir = Path(argv[1]).resolve()
    try:
        result = build_chain_summary(chain_dir)
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    s = result["summary"]
    print(f"[{s['chain']}] 보조 파일 생성 완료")
    print(f"  총 매장: {s['total_stores']}")
    print(f"  시도 수: {len(s['by_sido'])}")
    print(f"  월별 파일: {len(s['monthly_files'])}")
    print(f"  폐점 후보: {result['closure_count']}")
    print(f"  → {result['summary_path'].name}")
    print(f"  → {result['index_path'].name}")
    print(f"  → {result['closure_path'].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
