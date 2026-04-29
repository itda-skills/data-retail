"""
SPEC-GS25-001: GS25 매장 정보 수집 스크립트
4단계 발견 파이프라인(부트스트랩 → 시도 → 군구 → 동 → 매장)을 실행하여
전체 GS25 매장 데이터를 수집하고 월별 CSV로 누적 저장한다.
_latest.csv를 atomic rename으로 갱신한다.
"""

import argparse
import csv
import json
import os
import re
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

BASE_URL = "https://gs25.gsretail.com/gscvs/ko"

# 부트스트랩 페이지 URL (CSRFToken + 쿠키 jar + 시도 목록)
BOOTSTRAP_URL = f"{BASE_URL}/store-services/locations"

# 군구 발견 API
GUNGU_URL = f"{BASE_URL}/gsapi/gis/searchGungu"

# 동 발견 API
DONG_URL = f"{BASE_URL}/gsapi/gis/searchDong"

# 매장 검색 API (이중 JSON 응답)
LOCATION_LIST_URL = f"{BASE_URL}/store-services/locationList"

# HTTP 헤더 — Chrome UA만 사용 (레포 URL 비포함, REQ-GS25-002)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Referer": BOOTSTRAP_URL,
    "X-Requested-With": "XMLHttpRequest",
}

# CSRFToken 추출 정규식 (REQ-GS25-002)
CSRF_TOKEN_RE = re.compile(r'ACC\.config\.CSRFToken\s*=\s*"([^"]+)"')

# 시도 select (id="stb1") 영역 추출 정규식
SIDO_SELECT_RE = re.compile(r'id="stb1"[^>]*>(.*?)</select>', re.DOTALL)
SIDO_OPTION_RE = re.compile(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>')

# 22종 서비스 플래그 화이트리스트 (REQ-GS25-005)
# @MX:NOTE: [AUTO] 22종 서비스 코드는 SPEC-GS25-001에서 고정. 신규 코드는 WARN 로깅 후 services 컬럼에만 보존.
SERVICE_WHITELIST = [
    "cafe25", "instant", "drug", "post", "withdrawal", "atm", "taxrefund",
    "smart_atm", "self_cooking_utensils", "delivery_service", "parcel_service",
    "potatoes", "cardiac_defi", "fish_shaped_bun", "wine25", "go_pizza",
    "spirit_wine", "fresh_ganghw", "musinsa", "posa", "toto", "self25",
]

# 월별 CSV 컬럼 (30개)
MONTHLY_COLUMNS = [
    "code",
    "title",
    "address",
    "lat",
    "lng",
    "services",
    "svc_cafe25",
    "svc_instant",
    "svc_drug",
    "svc_post",
    "svc_withdrawal",
    "svc_atm",
    "svc_taxrefund",
    "svc_smart_atm",
    "svc_self_cooking_utensils",
    "svc_delivery_service",
    "svc_parcel_service",
    "svc_potatoes",
    "svc_cardiac_defi",
    "svc_fish_shaped_bun",
    "svc_wine25",
    "svc_go_pizza",
    "svc_spirit_wine",
    "svc_fresh_ganghw",
    "svc_musinsa",
    "svc_posa",
    "svc_toto",
    "svc_self25",
    "first_seen_at",
    "last_seen_at",
]

# _latest.csv 컬럼 (31개 = 월별 30개 + current_month_file)
LATEST_COLUMNS = MONTHLY_COLUMNS + ["current_month_file"]

# 갱신 대상 필드 (보존 필드: code, first_seen_at)
UPDATE_FIELDS = [
    "title",
    "address",
    "lat",
    "lng",
    "services",
    "svc_cafe25", "svc_instant", "svc_drug", "svc_post", "svc_withdrawal",
    "svc_atm", "svc_taxrefund", "svc_smart_atm", "svc_self_cooking_utensils",
    "svc_delivery_service", "svc_parcel_service", "svc_potatoes",
    "svc_cardiac_defi", "svc_fish_shaped_bun", "svc_wine25", "svc_go_pizza",
    "svc_spirit_wine", "svc_fresh_ganghw", "svc_musinsa", "svc_posa",
    "svc_toto", "svc_self25",
    "last_seen_at",
]

# 5xx 지수 백오프 대기 시간(초)
BACKOFF_WAIT = [1, 2, 4]


# ---------------------------------------------------------------------------
# 부트스트랩 세션 (Step 0) — REQ-GS25-002
# ---------------------------------------------------------------------------


# @MX:ANCHOR: [AUTO] 세션 초기화 + CSRFToken + 시도 목록 반환. 모든 후속 호출의 선제조건.
# @MX:REASON: bootstrap_session은 fetch_gungu, fetch_dong, fetch_stores, main에서 호출됨 (fan_in >= 3)
def bootstrap_session(session) -> tuple:
    """
    GET /store-services/locations 를 호출하여 세션 부트스트랩을 수행한다.
    CSRFToken과 시도(sido) 목록을 반환한다.
    토큰 미발견 또는 시도 0건이면 즉시 RuntimeError를 발생시킨다 (fail-fast).

    Args:
        session: requests.Session 인스턴스

    Returns:
        (csrf_token, [(sido_code, sido_name), ...]) 튜플

    Raises:
        RuntimeError: CSRFToken 미발견 또는 시도 파싱 0건
    """
    resp = session.get(BOOTSTRAP_URL, headers=HEADERS, timeout=30)

    if resp.status_code >= 400:
        raise RuntimeError(
            f"부트스트랩 HTTP 오류: {resp.status_code}. 응답: {resp.text[:200]}"
        )

    html = resp.text

    # CSRFToken 추출 (REQ-GS25-002)
    token_match = CSRF_TOKEN_RE.search(html)
    if not token_match:
        raise RuntimeError(
            "CSRFToken을 찾을 수 없습니다. HTML 구조가 변경되었을 수 있습니다."
        )
    csrf_token = token_match.group(1)

    # 시도 목록 파싱 — id="stb1" select 영역
    sido_section_match = SIDO_SELECT_RE.search(html)
    if not sido_section_match:
        raise RuntimeError(
            "시도 select(id='stb1')를 찾을 수 없습니다. HTML 구조가 변경되었을 수 있습니다."
        )

    sido_section = sido_section_match.group(1)
    sidos = [
        (code, name.strip())
        for code, name in SIDO_OPTION_RE.findall(sido_section)
        if code  # value="" 빈 옵션 제외
    ]

    if not sidos:
        raise RuntimeError(
            "시도 옵션이 0건입니다. HTML 구조가 변경되었을 수 있습니다."
        )

    return csrf_token, sidos


# ---------------------------------------------------------------------------
# 군구 발견 (Step 2) — REQ-GS25-003
# ---------------------------------------------------------------------------


def fetch_gungu(session, sido_code: str, delay: float = 0.5) -> list:
    """
    시도별 군구 목록을 발견한다.
    5xx/타임아웃 시 지수 백오프 3회. 4xx 즉시 실패.
    resultCode != "00000" 이면 즉시 실패.

    Args:
        session: requests.Session
        sido_code: 시도 코드 문자열 (예: "11")
        delay: HTTP 호출 전 sleep 초

    Returns:
        [(gungu_code, gungu_name), ...] 리스트
    """
    time.sleep(delay)

    params = {"stb1": sido_code}
    resp = _get_with_retry(session, GUNGU_URL, params=params)

    data = resp.json()

    # resultCode 검증 (REQ-GS25-003)
    result_code = data.get("resultCode")
    if result_code is not None and result_code != "00000":
        raise RuntimeError(
            f"searchGungu resultCode 오류: {result_code}. 응답: {data}"
        )

    result = data.get("result", [])
    return [(item[0], item[1]) for item in result if item]


# ---------------------------------------------------------------------------
# 동 발견 (Step 3) — REQ-GS25-003
# ---------------------------------------------------------------------------


def fetch_dong(session, sido_code: str, gungu_code: str, delay: float = 0.5) -> list:
    """
    군구별 동 목록을 발견한다.
    5xx/타임아웃 시 지수 백오프 3회. 4xx 즉시 실패.
    resultCode != "00000" 이면 즉시 실패.

    Args:
        session: requests.Session
        sido_code: 시도 코드
        gungu_code: 군구 코드
        delay: HTTP 호출 전 sleep 초

    Returns:
        [(dong_code, dong_name), ...] 리스트
    """
    time.sleep(delay)

    params = {"stb1": sido_code, "stb2": gungu_code}
    resp = _get_with_retry(session, DONG_URL, params=params)

    data = resp.json()

    result_code = data.get("resultCode")
    if result_code is not None and result_code != "00000":
        raise RuntimeError(
            f"searchDong resultCode 오류: {result_code}. 응답: {data}"
        )

    result = data.get("result", [])
    return [(item[0], item[1]) for item in result if item]


# ---------------------------------------------------------------------------
# 매장 검색 (Step 4) — REQ-GS25-004
# ---------------------------------------------------------------------------


# @MX:WARN: [AUTO] 이중 JSON 디코딩 로직. API 응답 형식 변경 시 이 함수가 즉시 실패한다.
# @MX:REASON: json.loads(json.loads(raw)) 패턴은 비표준 인코딩 의존성을 가짐
def fetch_stores(
    session, csrf_token: str, sido: str, gungu: str, dong: str, delay: float = 0.5
) -> list:
    """
    동 단위 매장 목록을 POST locationList API로 수집하고 정규화하여 반환한다.
    이중 JSON 응답을 디코딩한다: json.loads(json.loads(raw)).
    5xx/타임아웃 시 백오프 3회. 4xx 즉시 실패.

    Args:
        session: requests.Session
        csrf_token: CSRFToken
        sido: 시도 코드
        gungu: 군구 코드
        dong: 동 코드
        delay: HTTP 호출 전 sleep 초

    Returns:
        정규화된 매장 딕셔너리 목록
    """
    time.sleep(delay)

    url = f"{LOCATION_LIST_URL}?CSRFToken={csrf_token}"
    headers = {
        **HEADERS,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    # 폼 데이터 — searchType*=0 으로 모두 고정 (전 매장 수집)
    form_data = (
        f"pageNum=1&pageSize=50000&searchShopName="
        f"&searchSido={sido}&searchGugun={gungu}&searchDong={dong}"
        f"&searchType=&searchTypeService=0"
        f"&searchTypeFreshGanghw=0&searchTypeMusinsa=0&searchTypePosa=0"
        f"&searchTypeWine25=0&searchTypeGoPizza=0&searchTypeSpiritWine=0"
        f"&searchTypeCardiacDefi=0&searchTypeFishShapedBun=0&searchTypeSmartAtm=0"
        f"&searchTypeSelfCookingUtensils=0&searchTypeDeliveryService=0"
        f"&searchTypeParcelService=0&searchTypePotatoes=0&searchTypeTaxrefund=0"
        f"&searchTypeWithdrawal=0&searchTypeATM=0&searchTypePost=0"
        f"&searchTypeSelf25=0&searchTypeDrug=0&searchTypeInstant=0"
        f"&searchTypeCafe25=0&searchTypeToto=0"
    )

    resp = _post_with_retry(session, url, data=form_data, headers=headers)

    # 이중 JSON 언랩 (REQ-GS25-004)
    raw_text = resp.text
    inner = json.loads(raw_text)
    if isinstance(inner, str):
        data = json.loads(inner)
    else:
        data = inner

    results = data.get("results", [])
    return [normalize_store(raw) for raw in results]


# ---------------------------------------------------------------------------
# 정규화 (REQ-GS25-005)
# ---------------------------------------------------------------------------


# @MX:ANCHOR: [AUTO] normalize_store는 lat/longs swap, services 매핑의 핵심 함수.
# @MX:REASON: fetch_stores, test_fetch_gs25, main에서 호출됨 (fan_in >= 3)
def normalize_store(raw: dict) -> dict:
    """
    GS25 API 원시 레코드를 CSV 스키마에 맞게 정규화한다.
    lat/longs 필드 의미 반전을 swap하고, services 플래그를 매핑한다.

    Args:
        raw: API 응답의 단일 매장 딕셔너리

    Returns:
        정규화된 매장 딕셔너리 (MONTHLY_COLUMNS 기준, first_seen_at/last_seen_at 제외)
    """
    offering = raw.get("offeringService", []) or []

    # services — 알파벳순 정렬 + 세미콜론 join
    services_str = ";".join(sorted(offering))

    # svc_* 매핑 — 화이트리스트 기반
    svc_flags = {}
    for code in offering:
        if code in SERVICE_WHITELIST:
            svc_flags[f"svc_{code}"] = 1
        else:
            # 미지의 서비스 코드 — services 컬럼에는 보존, svc_ 컬럼 미생성
            print(f"[WARN] unknown service code: {code}", file=sys.stderr)

    # 화이트리스트 전체 기본값 0
    for svc in SERVICE_WHITELIST:
        svc_flags.setdefault(f"svc_{svc}", 0)

    # GS25 API trap: lat/longs fields are inverted from their names.
    # API "lat" actually carries longitude, API "longs" actually carries latitude.
    lat_value = float(raw.get("longs", 0))   # API longs = 실제 위도
    lng_value = float(raw.get("lat", 0))     # API lat = 실제 경도

    return {
        "code": str(raw.get("shopCode", "")),  # 문자열 보존 (정수 변환 금지)
        "title": raw.get("shopName", ""),
        "address": raw.get("address", ""),
        "lat": lat_value,
        "lng": lng_value,
        "services": services_str,
        **svc_flags,
    }


# ---------------------------------------------------------------------------
# _latest.csv 로드 — REQ-GS25-006
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
# 신규 등록 월 결정 — REQ-GS25-006
# ---------------------------------------------------------------------------


def decide_destination(store: dict, latest_map: dict, today: date) -> tuple:
    """
    매장의 신규 등록 월 파일 경로와 first_seen_at을 결정한다.

    GS25는 OPEN_DATE가 없으므로 first_seen_at(오늘)을 파티션 키로 사용한다.
    이는 emart24의 OPEN_DATE 기반 파티션과 의도적으로 다른 설계 선택이다 (SPEC-GS25-001).

    - _latest.csv에 없으면(신규): first_seen_at = 오늘, 등록 월 = 오늘 기준
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

    # 신규 매장: first_seen_at = 오늘, 등록 월 = 오늘 연/월
    first_seen_at = str(today)
    month_file = today.strftime("%Y/%m")
    return month_file, first_seen_at


# ---------------------------------------------------------------------------
# _latest.csv 재작성 — REQ-GS25-005b
# ---------------------------------------------------------------------------


def rewrite_latest_csv(rows: list, path: Path) -> None:
    """
    _latest.csv를 임시 파일에 작성 후 atomic rename으로 교체한다.
    code ASC 정렬. 31개 컬럼.

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
            quoting=csv.QUOTE_NONNUMERIC,  # 비숫자 필드 따옴표, 숫자는 그대로
            lineterminator="\n",
        )
        writer.writeheader()
        for row in sorted_rows:
            row_copy = dict(row)
            row_copy["code"] = str(row_copy.get("code", ""))
            writer.writerow(row_copy)

    # atomic rename
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# 월별 CSV 갱신 — REQ-GS25-007
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
        base_dir: 체인 디렉터리 경로 (예: convenience/gs25/)
        today: 오늘 날짜

    Returns:
        통계 딕셔너리 {new: N, updated: M}
        각 store에 first_seen_at, last_seen_at, current_month_file 필드가 추가됨 (in-place)
    """
    stats = {"new": 0, "updated": 0}

    # 월별 파일별로 현재 행을 메모리에 로드
    monthly_data: dict = {}  # "YYYY/MM" → {code: row}

    for store in stores:
        code = store["code"]
        month_file, first_seen_at = decide_destination(store, latest_map, today)

        store["first_seen_at"] = first_seen_at
        store["last_seen_at"] = str(today)
        store["current_month_file"] = month_file

        if month_file not in monthly_data:
            csv_path = base_dir / f"{month_file}.csv"
            monthly_data[month_file] = _load_monthly_file(csv_path)

        if code in latest_map:
            # 기존 매장: 갱신
            if code in monthly_data[month_file]:
                _update_row(monthly_data[month_file][code], store)
            else:
                monthly_data[month_file][code] = store
            stats["updated"] += 1
        else:
            # 신규 매장: append
            monthly_data[month_file][code] = store
            stats["new"] += 1

    # 월별 CSV 저장
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
# 트랜잭션 실행 — REQ-GS25-011
# ---------------------------------------------------------------------------


def run_transaction(
    api_stores: list,
    latest_map: dict,
    base_dir: Path,
    today: date,
) -> Optional[dict]:
    """
    월별 CSV 갱신과 _latest.csv 재작성을 하나의 트랜잭션으로 실행한다.
    실패 시 롤백: tmp 파일 삭제.

    Args:
        api_stores: normalize_store() 결과 목록
        latest_map: load_latest_map() 결과
        base_dir: 체인 디렉터리 경로 (예: convenience/gs25/)
        today: 오늘 날짜

    Returns:
        성공 시 통계 딕셔너리, 실패 시 None
    """
    latest_path = base_dir / "_latest.csv"
    tmp_path = base_dir / "_latest.csv.tmp"

    try:
        # 1단계: 월별 CSV 갱신
        stats = update_monthly_csvs(api_stores, latest_map, base_dir, today)

        # 2단계: _latest.csv 재작성
        # 미관측 매장은 latest_map에서 유지 (last_seen_at 이전 값 보존)
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
# 내부 HTTP 헬퍼 — 지수 백오프 재시도
# ---------------------------------------------------------------------------


def _get_with_retry(session, url: str, params=None, max_retries: int = 3):
    """
    GET 요청을 지수 백오프로 재시도한다.
    4xx 즉시 실패. 5xx/타임아웃은 3회 재시도.
    """
    for attempt in range(max_retries):
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=30)

            if 400 <= resp.status_code < 500:
                raise RuntimeError(f"4xx 오류: {resp.status_code} — 즉시 실패")

            if resp.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(BACKOFF_WAIT[attempt])
                    continue
                raise RuntimeError(f"5xx 오류 {resp.status_code} 재시도 소진")

            return resp

        except RuntimeError:
            raise
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(BACKOFF_WAIT[attempt])
            else:
                raise RuntimeError(f"GET 요청 실패 ({url}): {exc}") from exc

    raise RuntimeError(f"GET 요청 재시도 소진: {url}")


def _post_with_retry(session, url: str, data: str, headers: dict, max_retries: int = 3):
    """
    POST 요청을 지수 백오프로 재시도한다.
    4xx 즉시 실패. 5xx/타임아웃은 3회 재시도.
    """
    for attempt in range(max_retries):
        try:
            resp = session.post(url, headers=headers, data=data, timeout=30)

            if 400 <= resp.status_code < 500:
                raise RuntimeError(f"4xx 오류: {resp.status_code} — 즉시 실패")

            if resp.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(BACKOFF_WAIT[attempt])
                    continue
                raise RuntimeError(f"5xx 오류 {resp.status_code} 재시도 소진")

            return resp

        except RuntimeError:
            raise
        except Exception as exc:
            if attempt < max_retries - 1:
                time.sleep(BACKOFF_WAIT[attempt])
            else:
                raise RuntimeError(f"POST 요청 실패 ({url}): {exc}") from exc

    raise RuntimeError(f"POST 요청 재시도 소진: {url}")


# ---------------------------------------------------------------------------
# 엔트리포인트 — REQ-GS25-001
# ---------------------------------------------------------------------------


def main(delay: float = 0.5, dry_run: bool = False) -> int:
    """
    GS25 매장 정보 수집 메인 함수.
    4단계 발견 파이프라인을 실행하고 CSV를 갱신한다.

    Args:
        delay: HTTP 호출 간 대기 초 (REQ-GS25-010)
        dry_run: True이면 CSV 파일을 저장하지 않음

    Returns:
        exit code (0=성공, 1=실패)
    """
    if requests is None:
        print("[오류] requests 라이브러리가 없습니다.", file=sys.stderr)
        return 1

    today = date.today()
    base_dir = Path(__file__).parent.parent / "convenience" / "gs25"
    latest_path = base_dir / "_latest.csv"

    # 1. _latest.csv 로드
    latest_map = load_latest_map(latest_path)
    print(f"[정보] _latest.csv 로드: {len(latest_map)}개 기존 매장")

    # 2. 세션 부트스트랩 (Step 0)
    session = requests.Session()
    try:
        csrf_token, sidos = bootstrap_session(session)
        print(f"[정보] 부트스트랩 완료. 시도 {len(sidos)}개, CSRFToken 획득")
        time.sleep(delay)
    except Exception as exc:
        print(f"[오류] 부트스트랩 실패: {exc}", file=sys.stderr)
        return 1

    # 3. 시도 → 군구 → 동 → 매장 발견
    all_raw_stores = []
    seen_codes: set = set()

    for sido_code, sido_name in sidos:
        print(f"[정보] 시도 {sido_code} ({sido_name}) 군구 발견 중...")
        try:
            gungus = fetch_gungu(session, sido_code, delay=delay)
        except Exception as exc:
            print(f"[오류] 군구 발견 실패 ({sido_name}): {exc}", file=sys.stderr)
            return 1

        for gungu_code, gungu_name in gungus:
            try:
                dongs = fetch_dong(session, sido_code, gungu_code, delay=delay)
            except Exception as exc:
                print(
                    f"[오류] 동 발견 실패 ({sido_name} {gungu_name}): {exc}",
                    file=sys.stderr,
                )
                return 1

            for dong_code, dong_name in dongs:
                try:
                    stores = fetch_stores(
                        session, csrf_token, sido_code, gungu_code, dong_code, delay=delay
                    )
                except Exception as exc:
                    print(
                        f"[오류] 매장 수집 실패 ({sido_name} {gungu_name} {dong_name}): {exc}",
                        file=sys.stderr,
                    )
                    return 1

                # 중복 code 검증 (REQ-GS25-005)
                for store in stores:
                    code = store["code"]
                    if code in seen_codes:
                        print(f"[오류] 중복 code 발견: {code}", file=sys.stderr)
                        return 1
                    seen_codes.add(code)

                all_raw_stores.extend(stores)

    print(f"[정보] 총 {len(all_raw_stores)}개 매장 수집")

    if dry_run:
        print("[정보] dry_run 모드. CSV 저장 건너뜀.")
        return 0

    # 4. 트랜잭션 실행
    stats = run_transaction(all_raw_stores, latest_map, base_dir, today)

    if stats is None:
        return 1

    unobserved = len(latest_map) - stats["updated"]
    print(
        f"[완료] 신규={stats['new']}, 갱신={stats['updated']}, "
        f"미관측={max(0, unobserved)}"
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GS25 매장 정보 수집")
    parser.add_argument("--delay", type=float, default=0.5, help="HTTP 호출 간 대기 초")
    parser.add_argument("--dry-run", action="store_true", help="CSV 파일을 저장하지 않음")
    args = parser.parse_args()

    sys.exit(main(delay=args.delay, dry_run=args.dry_run))
