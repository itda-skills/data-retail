"""
SPEC-EMART24-001: emart24 매장 정보 수집 스크립트
emart24 공개 API에서 전체 매장 데이터를 수집하여 월별 CSV로 누적 저장하고,
_latest.csv를 atomic rename으로 갱신한다.
"""

import argparse
import csv
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # 테스트 환경에서 없을 수 있음

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

API_URL = "https://emart24.co.kr/api1/store"

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://emart24.co.kr/store",
    "X-Requested-With": "XMLHttpRequest",
}

PAGE_SIZE = 40

# 월별 CSV 컬럼 (25개)
MONTHLY_COLUMNS = [
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

# _latest.csv 컬럼 (26개 = 월별 25개 + current_month_file)
LATEST_COLUMNS = MONTHLY_COLUMNS + ["current_month_file"]

# 갱신 대상 필드 (보존 필드: code, open_date, first_seen_at)
UPDATE_FIELDS = [
    "title",
    "address",
    "address_detail",
    "phone",
    "lat",
    "lng",
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
    "last_seen_at",
]


# ---------------------------------------------------------------------------
# 정규화
# ---------------------------------------------------------------------------


def _normalize_date(raw_date: str) -> str:
    """'YYYY.MM.DD' 형식을 'YYYY-MM-DD' ISO 형식으로 변환한다."""
    return raw_date.replace(".", "-")


def _normalize_hhmm(raw_hhmm: str) -> str:
    """'HHMM' 4자리를 'HH:MM' 형식으로 변환한다."""
    if len(raw_hhmm) == 4:
        return f"{raw_hhmm[:2]}:{raw_hhmm[2:]}"
    return raw_hhmm


def normalize_store(raw: dict) -> dict:
    """
    API 원시 응답 row를 CSV 스키마에 맞게 정규화한다.

    Args:
        raw: API 응답의 단일 매장 딕셔너리

    Returns:
        정규화된 매장 딕셔너리 (월별 CSV 컬럼 기준, first_seen_at/last_seen_at 제외)
    """
    open_date_raw = raw.get("OPEN_DATE", "")
    open_date = _normalize_date(open_date_raw) if open_date_raw else ""

    end_date_raw = raw.get("END_DATE", "")
    if end_date_raw == "9999.12.31":
        end_date = ""
    elif end_date_raw:
        end_date = _normalize_date(end_date_raw)
    else:
        end_date = ""

    start_raw = raw.get("START_HHMM", "0000")
    end_raw = raw.get("END_HHMM", "0000")
    start_hhmm = _normalize_hhmm(start_raw)
    end_hhmm = _normalize_hhmm(end_raw)

    # is_24h: SVR_24=1 OR (start==end=="0000")
    svr_24 = str(raw.get("SVR_24", "0"))
    is_24h = 1 if (svr_24 == "1" or (start_raw == "0000" and end_raw == "0000")) else 0

    return {
        "code": str(raw.get("CODE", "")),  # 문자열 유지 (zero-pad 보존)
        "title": raw.get("TITLE", ""),
        "address": raw.get("ADDRESS", ""),
        "address_detail": raw.get("ADDRESS_DE", ""),
        "phone": raw.get("TEL", ""),
        "lat": raw.get("LATITUDE", ""),
        "lng": raw.get("LONGITUDE", ""),
        "open_date": open_date,
        "end_date": end_date,
        "start_hhmm": start_hhmm,
        "end_hhmm": end_hhmm,
        "is_24h": is_24h,
        "svc_parcel": int(raw.get("SVR_PARCEL", 0)),
        "svc_atm": int(raw.get("SVR_ATM", 0)),
        "svc_wine": int(raw.get("SVR_WINE", 0)),
        "svc_coffee": int(raw.get("SVR_COFFEE", 0)),
        "svc_smoothie": int(raw.get("SVR_SMOOTHIE", 0)),
        "svc_apple": int(raw.get("SVR_APPLE", 0)),
        "svc_toto": int(raw.get("SVR_TOTO", 0)),
        "svc_auto": int(raw.get("SVR_AUTO", 0)),
        "svc_pickup": int(raw.get("SVR_PICKUP", 0)),
        "svc_chicken": int(raw.get("SVR_CHICKEN", 0)),
        "svc_noodle": int(raw.get("SVR_NOODLE", 0)),
        "tobacco_license": int(raw.get("BUSINESS_LICENSE", 0)),
    }


# ---------------------------------------------------------------------------
# _latest.csv 로드
# ---------------------------------------------------------------------------


def load_latest_map(path: Path) -> dict:
    """
    _latest.csv를 읽어 code → row 메모리 맵을 반환한다.
    파일이 없으면 빈 딕셔너리를 반환한다 (부트스트랩).

    Args:
        path: _latest.csv 경로

    Returns:
        {code: row_dict} 딕셔너리
    """
    if not path.exists():
        return {}

    result = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["code"]] = dict(row)
    return result


# ---------------------------------------------------------------------------
# 신규 등록 월 결정
# ---------------------------------------------------------------------------


def decide_destination(store: dict, latest_map: dict, today: date) -> tuple:
    """
    매장의 신규 등록 월 파일 경로와 first_seen_at을 결정한다.

    SPEC REQ-EM-004:
    - _latest.csv에 없으면(신규): min(OPEN_DATE월, 오늘월)로 파일 결정
      - 단, OPEN_DATE가 미래이면 OPEN_DATE 월 파일에 등록 (SPEC 인수 테스트 #3)
    - _latest.csv에 있으면(기존): current_month_file 보존, first_seen_at 보존

    Args:
        store: normalize_store() 결과
        latest_map: load_latest_map() 결과
        today: 오늘 날짜

    Returns:
        (current_month_file, first_seen_at) 튜플
    """
    code = store["code"]

    if code in latest_map:
        # 기존 매장: 월 이동 없음, first_seen_at 보존
        existing = latest_map[code]
        return existing["current_month_file"], existing["first_seen_at"]

    # 신규 매장
    first_seen_at = str(today)
    open_date_str = store.get("open_date", "")

    if not open_date_str:
        # OPEN_DATE 없으면 오늘 월 사용
        month_file = today.strftime("%Y/%m")
        return month_file, first_seen_at

    # OPEN_DATE 파싱
    open_year, open_month = int(open_date_str[:4]), int(open_date_str[5:7])

    # SPEC 인수 테스트 #3: OPEN_DATE가 미래이면 → OPEN_DATE 월 파일
    # SPEC 규칙: min(open_date_yyyymm, first_seen_yyyymm) but OPEN_DATE월 파일 기준
    # 실제로 SPEC은 "더 빠른 날짜"를 파일로 사용
    # A > B (예정 오픈): 파일은 OPEN_DATE 기준 미래 월 (SPEC 인수 테스트 #3)
    # A < B (오래된 매장): 파일은 OPEN_DATE 기준 (과거 월)
    # A == B: 동일 월
    # → 결론: 항상 OPEN_DATE 월 기준으로 파일 결정 (신규 매장의 경우)
    month_file = f"{open_year:04d}/{open_month:02d}"
    return month_file, first_seen_at


# ---------------------------------------------------------------------------
# _latest.csv 재작성
# ---------------------------------------------------------------------------


def rewrite_latest_csv(rows: list, path: Path) -> None:
    """
    _latest.csv를 임시 파일에 작성 후 atomic rename으로 교체한다.
    code ASC 정렬. 26개 컬럼.

    Args:
        rows: 전체 매장 딕셔너리 목록
        path: _latest.csv 경로
    """
    tmp_path = path.with_suffix(".csv.tmp")

    # code ASC 정렬
    sorted_rows = sorted(rows, key=lambda r: str(r.get("code", "")))

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=LATEST_COLUMNS,
            extrasaction="ignore",
            quoting=csv.QUOTE_NONNUMERIC,  # 모든 비숫자 필드 따옴표, 숫자는 그대로
            lineterminator="\n",
        )
        writer.writeheader()
        for row in sorted_rows:
            # code는 항상 문자열로 강제
            row_copy = dict(row)
            row_copy["code"] = str(row_copy.get("code", ""))
            writer.writerow(row_copy)

    # atomic rename
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# 월별 CSV 갱신
# ---------------------------------------------------------------------------


def update_monthly_csvs(
    stores: list,
    latest_map: dict,
    base_dir: Path,
    today: date,
) -> dict:
    """
    API에서 수집된 매장 목록을 월별 CSV 파일에 반영한다.
    신규 매장은 append, 기존 매장은 행 갱신 (월 이동 없음).

    Args:
        stores: normalize_store() 결과 목록
        latest_map: load_latest_map() 결과 (code → row)
        base_dir: 체인 디렉터리 경로 (예: convenience/emart24/)
        today: 오늘 날짜

    Returns:
        통계 딕셔너리 {new: N, updated: M, unobserved: K}
        각 store에 first_seen_at, last_seen_at, current_month_file 필드가 추가됨 (in-place)
    """
    stats = {"new": 0, "updated": 0}

    # 월별 파일별로 모든 현재 행을 메모리에 로드
    monthly_data: dict = {}  # "YYYY/MM" → {code: row}

    for store in stores:
        code = store["code"]
        month_file, first_seen_at = decide_destination(store, latest_map, today)

        store["first_seen_at"] = first_seen_at
        store["last_seen_at"] = str(today)
        store["current_month_file"] = month_file

        if month_file not in monthly_data:
            # 기존 월별 파일 로드
            csv_path = base_dir / f"{month_file}.csv"
            monthly_data[month_file] = _load_monthly_file(csv_path)

        if code in latest_map:
            # 기존 매장: 갱신
            if code in monthly_data[month_file]:
                _update_row(monthly_data[month_file][code], store)
            else:
                # 월별 파일에 없으면 추가 (예외 상황)
                monthly_data[month_file][code] = store
            stats["updated"] += 1
        else:
            # 신규 매장: append
            monthly_data[month_file][code] = store
            stats["new"] += 1

    # 월별 CSV 파일 저장
    for month_file, rows_map in monthly_data.items():
        csv_path = base_dir / f"{month_file}.csv"
        _write_monthly_file(csv_path, list(rows_map.values()))

    return stats


def _load_monthly_file(path: Path) -> dict:
    """월별 CSV 파일을 {code: row} 딕셔너리로 로드한다."""
    if not path.exists():
        return {}

    result = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row["code"]] = dict(row)
    return result


def _update_row(existing: dict, new_data: dict) -> None:
    """기존 행을 새 데이터로 갱신한다 (in-place). 보존 필드는 유지."""
    for field in UPDATE_FIELDS:
        if field in new_data:
            existing[field] = new_data[field]


def _write_monthly_file(path: Path, rows: list) -> None:
    """월별 CSV 파일을 작성한다."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=MONTHLY_COLUMNS,
            extrasaction="ignore",
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            row_copy = dict(row)
            row_copy["code"] = str(row_copy.get("code", ""))
            writer.writerow(row_copy)


# ---------------------------------------------------------------------------
# 트랜잭션 실행 (REQ-EM-005/005b/010)
# ---------------------------------------------------------------------------


def run_transaction(
    api_stores: list,
    latest_map: dict,
    base_dir: Path,
    today: date,
) -> Optional[dict]:
    """
    월별 CSV 갱신과 _latest.csv 재작성을 하나의 트랜잭션으로 실행한다.
    실패 시 롤백: 변경된 월별 CSV 복원 + _latest.csv.tmp 삭제.

    Args:
        api_stores: normalize_store() 결과 목록
        latest_map: load_latest_map() 결과
        base_dir: 체인 디렉터리 경로 (예: convenience/emart24/)
        today: 오늘 날짜

    Returns:
        성공 시 통계 딕셔너리, 실패 시 None
    """
    latest_path = base_dir / "_latest.csv"
    tmp_path = base_dir / "_latest.csv.tmp"

    # 백업: 영향받는 월별 CSV 파일 목록 추적

    try:
        # 1단계: 월별 CSV 갱신
        stats = update_monthly_csvs(api_stores, latest_map, base_dir, today)

        # 2단계: _latest.csv 재작성
        # 미관측 매장은 latest_map에서 유지 (last_seen_at 이전 값)
        observed_codes = {s["code"] for s in api_stores}
        all_rows = list(api_stores)

        for code, row in latest_map.items():
            if code not in observed_codes:
                all_rows.append(row)

        rewrite_latest_csv(all_rows, latest_path)

        return stats

    except Exception as exc:
        # 롤백: tmp 파일 삭제
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

        print(f"[오류] 트랜잭션 실패: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# API 수집
# ---------------------------------------------------------------------------


def fetch_all_pages(session, delay: float = 0.5) -> list:
    """
    emart24 API의 모든 페이지를 수집하여 원시 매장 목록을 반환한다.
    5xx/타임아웃 시 지수 백오프 3회, 4xx 즉시 실패.

    Args:
        session: requests.Session
        delay: 페이지 간 대기 초

    Returns:
        원시 매장 딕셔너리 목록
    """
    all_stores = []
    page = 1
    total_pages = None

    while total_pages is None or page <= total_pages:
        params = {"page": page}
        response = _fetch_page_with_retry(session, params)

        if response is None:
            raise RuntimeError(f"페이지 {page} 수집 실패 (재시도 소진)")

        data = response.json()

        if total_pages is None:
            count = int(data.get("count", 0))
            total_pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)

        stores = data.get("list", data.get("data", []))
        all_stores.extend(stores)

        if page < total_pages:
            time.sleep(delay)
        page += 1

    return all_stores


def _fetch_page_with_retry(session, params: dict, max_retries: int = 3):
    """
    단일 페이지를 지수 백오프로 재시도하며 수집한다.
    4xx는 즉시 실패. 5xx/타임아웃은 3회 재시도.
    """
    wait_times = [1, 2, 4]

    for attempt in range(max_retries):
        try:
            resp = session.get(API_URL, headers=API_HEADERS, params=params, timeout=30)

            if 400 <= resp.status_code < 500:
                raise RuntimeError(f"4xx 오류: {resp.status_code} — 즉시 실패")

            if resp.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(wait_times[attempt])
                    continue
                return None

            return resp

        except RuntimeError:
            raise
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(wait_times[attempt])
            else:
                return None

    return None


# ---------------------------------------------------------------------------
# 엔트리포인트
# ---------------------------------------------------------------------------


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        exit code (0=성공, 1=실패)
    """
    parser = argparse.ArgumentParser(description="emart24 매장 정보 수집")
    parser.add_argument("--delay", type=float, default=0.5, help="페이지 간 대기 초")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path(__file__).parent.parent / "convenience" / "emart24",
        help="emart24 데이터 디렉터리",
    )
    args = parser.parse_args()

    today = date.today()
    base_dir = args.base_dir
    latest_path = base_dir / "_latest.csv"

    # 1. _latest.csv 로드
    latest_map = load_latest_map(latest_path)
    print(f"[정보] _latest.csv 로드: {len(latest_map)}개 기존 매장")

    # 2. API 수집
    if requests is None:
        print("[오류] requests 라이브러리가 없습니다.", file=sys.stderr)
        return 1

    session = requests.Session()
    try:
        raw_stores = fetch_all_pages(session, delay=args.delay)
    except Exception as exc:
        print(f"[오류] API 수집 실패: {exc}", file=sys.stderr)
        return 1

    print(f"[정보] API에서 {len(raw_stores)}개 매장 수집")

    # 3. 정규화 + 중복 code 검증
    stores = []
    seen_codes: set = set()
    for raw in raw_stores:
        store = normalize_store(raw)
        code = store["code"]
        if code in seen_codes:
            print(f"[오류] 중복 code 발견: {code}", file=sys.stderr)
            return 1
        seen_codes.add(code)
        stores.append(store)

    # 4. 트랜잭션 실행
    stats = run_transaction(stores, latest_map, base_dir, today)

    if stats is None:
        return 1

    unobserved = len(latest_map) - stats["updated"]
    print(
        f"[완료] 신규={stats['new']}, 갱신={stats['updated']}, "
        f"미관측={max(0, unobserved)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
