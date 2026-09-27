import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

WINNING_CRITERIA = {
    1: "당첨번호 6개 숫자일치",
    2: "당첨번호 5개 숫자일치+보너스 숫자일치",
    3: "당첨번호 5개 숫자일치",
    4: "당첨번호 4개 숫자일치",
    5: "당첨번호 3개 숫자일치",
}

HEADERS = {
    "AJAX": "true",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.dhlottery.co.kr/lt645/result",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/145.0.0.0 Safari/537.36"
    ),
}

# 지급기한은 회차별로 다르지 않은 고정 안내 문구다(기존 1204개 회차가 모두 이 값).
PAYMENT_DEADLINE = "지급개시일로부터 1년 (휴일인 경우 익영업일)"

# 1등 당첨 구매방식 집계. API의 winType1/2/3에 대응한다.
WIN_TYPE_LABELS = ((1, "자동"), (2, "수동"), (3, "반자동"))

KST = timezone(timedelta(hours=9))

# 추첨 방송 예정 시각(KST). 편성 변경으로 실제 방송이 늦어질 수 있으므로 기준점으로만 쓴다.
DRAW_AIR_TIME = timedelta(hours=20, minutes=45)

# 추첨일로부터 이 시간이 지나도 집계가 0이면 단순 지연이 아니라 이상으로 본다.
# 방송이 몇 시간 늦어지는 경우(예: 2026-09-26 아시안게임 중계로 22:30 이후 방송)를
# 넉넉히 흡수하면서, 며칠씩 방치되는 상황은 놓치지 않는 값이다.
TALLY_GRACE = timedelta(hours=24)

REQUEST_TIMEOUT = 10  # 초. 동행복권이 느릴 때 무한정 매달리지 않도록 반드시 지정한다.

# 아직 추첨/게시되지 않은 회차를 요청했을 때 쓰는 종료 코드.
# 오류(1)와 구분해야 워크플로가 "정상 스킵"과 "진짜 실패"를 구별할 수 있다.
EXIT_NOT_PUBLISHED = 75


class DrawNotPublished(Exception):
    """해당 회차가 아직 게시되지 않음(오류가 아님)."""


def build_session() -> requests.Session:
    """일시적 네트워크 오류/5xx에 대해 백오프 재시도하는 세션을 만듭니다."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,  # 1s, 2s, 4s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def get_json(session: requests.Session, url: str) -> dict:
    """JSON 응답을 가져옵니다. 리다이렉트로 엉뚱한 페이지에 도착한 경우도 오류로 처리합니다."""
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        raise ValueError(
            f"JSON 응답이 아닙니다. url={response.url} "
            f"status={response.status_code} content-type={content_type!r}"
        )
    return response.json()


def parse_date(ymd: str) -> str:
    """'20260307' -> '2026-03-07'"""
    return datetime.strptime(ymd, "%Y%m%d").strftime("%Y-%m-%d")


def fetch_round_list(session: requests.Session, drw_no: int) -> list:
    """요청 회차를 중심으로 한 회차 목록을 반환합니다. 범위를 벗어나면 빈 목록이 온다."""
    url = (
        f"https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
        f"?srchDir=center&srchLtEpsd={drw_no}"
    )
    data = get_json(session, url)
    return data.get("data", {}).get("list", [])


def round_exists(session: requests.Session, drw_no: int) -> bool:
    """해당 회차가 동행복권에 게시되어 있는지 확인합니다."""
    if drw_no < 1:
        return False
    return any(int(i["ltEpsd"]) == drw_no for i in fetch_round_list(session, drw_no))


def fetch_draw_info(session: requests.Session, drw_no: int) -> dict:
    """
    selectPstLt645InfoNew.do API에서 특정 회차 데이터를 반환합니다.
    요청 회차를 중심으로 여러 회차를 반환하므로 정확히 일치하는 회차만 골라 반환합니다.

    요청 회차를 찾지 못하면 상황에 따라 다음과 같이 구분한다.
      - 아직 게시되지 않음  -> DrawNotPublished (정상 스킵)
      - 그 외              -> ValueError (실패로 드러냄)

    이전 구현은 회차를 못 찾으면 '최신 회차'로 폴백했는데, 그러면 다른 회차의
    당첨번호가 요청 회차 번호로 저장되어 데이터가 조용히 오염된다.
    """
    lt645_list = fetch_round_list(session, drw_no)

    for item in lt645_list:
        if int(item["ltEpsd"]) == drw_no:
            return item

    if lt645_list:
        available = sorted(int(i["ltEpsd"]) for i in lt645_list)
        if drw_no > available[-1]:
            raise DrawNotPublished(
                f"{drw_no}회차는 아직 게시되지 않았습니다. (API 최신 회차: {available[-1]})"
            )
        raise ValueError(
            f"{drw_no}회차가 API 응답에 없습니다. (응답에 포함된 회차: {available[0]}~{available[-1]})"
        )

    # 목록이 비어 있으면 '미게시 회차'와 'API 이상' 둘 다 가능하다.
    # 직전 회차를 한 번 더 조회해 API 자체가 살아있는지 확인하여 구분한다.
    if drw_no > 1:
        probe = fetch_round_list(session, drw_no - 1)
        if any(int(i["ltEpsd"]) == drw_no - 1 for i in probe):
            raise DrawNotPublished(
                f"{drw_no}회차는 아직 게시되지 않았습니다. (직전 {drw_no - 1}회차는 정상 조회됨)"
            )

    raise ValueError(
        f"API 응답의 회차 목록이 비어 있습니다. (요청 회차: {drw_no}) "
        f"동행복권 API 이상이거나 응답 형식이 바뀌었을 수 있습니다."
    )


def build_note(item: dict) -> str:
    """
    1등 당첨자의 구매방식 집계를 구버전과 같은 문구로 만든다.
    예) winType1=8, winType2=3, winType3=1 -> "1등 자동8 수동3 반자동1"
    1등 당첨자가 없으면 빈 문자열을 반환한다.
    """
    parts = [
        f"{label}{item.get(f'winType{idx}', 0)}"
        for idx, label in WIN_TYPE_LABELS
        if item.get(f'winType{idx}', 0)
    ]
    return f"1등 {' '.join(parts)}" if parts else ""


def ensure_tally_complete(item: dict, drw_no: int) -> None:
    """
    추첨번호는 나왔지만 당첨자/판매금액 집계가 아직 끝나지 않은 상태를 걸러낸다.

    이 구간에 받은 데이터를 저장해 버리면 상금이 전부 0인 파일이 만들어지고,
    파일이 존재한다는 이유로 다시는 갱신되지 않아 영구히 0으로 굳는다.
    (실제로 1216~1218, 1226, 1230, 1235~1236, 1238회가 이렇게 손상됐다.)

    1등 당첨자 수는 0이 정상인 회차가 존재하므로(1, 4, 5, 7~9, 13, 18, 24, 41, 71회)
    판별 기준으로 쓸 수 없다. 5등 당첨자 수와 총판매금액은 정상 회차에서 0이 될 수 없다.
    """
    if item.get("rnk5WnNope") and item.get("rlvtEpsdSumNtslAmt"):
        return

    detail = (
        f"5등 당첨자수={item.get('rnk5WnNope')}, "
        f"총판매금액={item.get('rlvtEpsdSumNtslAmt')}"
    )

    # 추첨일로부터 얼마나 지났는지로 '단순 지연'과 '이상'을 가른다.
    # 지연이면 조용히 스킵하고 다음 실행에서 다시 받으면 되지만,
    # 하루가 넘도록 집계가 0이면 사람이 알아야 한다.
    try:
        aired_at = datetime.strptime(item["ltRflYmd"], "%Y%m%d").replace(tzinfo=KST) + DRAW_AIR_TIME
    except Exception as e:
        # 추첨일을 읽을 수 없으면 얼마나 지연됐는지 판단할 수 없다.
        # 조용히 스킵하면 영구히 묻히므로 실패로 올린다.
        raise ValueError(
            f"{drw_no}회차의 추첨일(ltRflYmd={item.get('ltRflYmd')!r})을 해석할 수 없습니다: {e} ({detail})"
        )

    elapsed = datetime.now(KST) - aired_at
    if elapsed > TALLY_GRACE:
        raise ValueError(
            f"{drw_no}회차는 추첨일로부터 {elapsed.total_seconds() / 3600:.1f}시간이 지났는데도 "
            f"집계가 반영되지 않았습니다. ({detail})"
        )

    raise DrawNotPublished(
        f"{drw_no}회차는 당첨 집계가 아직 반영되지 않았습니다. ({detail})"
    )


def build_draw_data(item: dict, drw_no: int) -> dict:
    """API 응답 항목을 저장 형식으로 변환합니다."""
    rank_details = []
    for rank in range(1, 6):
        rank_details.append({
            "rank": rank,
            "total_prize_amount": item.get(f"rnk{rank}SumWnAmt", 0),
            "num_winners": item.get(f"rnk{rank}WnNope", 0),
            "prize_per_game": item.get(f"rnk{rank}WnAmt", 0),
            "winning_criteria": WINNING_CRITERIA[rank],
        })

    return {
        "draw_no": drw_no,
        "draw_date": parse_date(item["ltRflYmd"]),
        "winning_numbers": [
            item["tm1WnNo"], item["tm2WnNo"], item["tm3WnNo"],
            item["tm4WnNo"], item["tm5WnNo"], item["tm6WnNo"],
        ],
        "bonus_number": item["bnsWnNo"],
        "rank_details": rank_details,
        "note": build_note(item),
        "misc_info": {
            "payment_deadline": PAYMENT_DEADLINE,
            "total_sales_amount": item.get("rlvtEpsdSumNtslAmt", 0),
        },
    }


def validate_draw_data(data: dict, drw_no: int) -> None:
    """저장 전 최소 무결성 검사. 하나라도 어긋나면 파일을 쓰지 않는다."""
    if data["draw_no"] != drw_no:
        raise ValueError(f"회차 불일치: 요청={drw_no} 데이터={data['draw_no']}")

    numbers = data["winning_numbers"]
    if len(numbers) != 6:
        raise ValueError(f"당첨번호가 6개가 아닙니다: {numbers}")
    if not all(isinstance(n, int) and 1 <= n <= 45 for n in numbers):
        raise ValueError(f"당첨번호 범위(1~45)를 벗어났습니다: {numbers}")
    if len(set(numbers)) != 6:
        raise ValueError(f"당첨번호에 중복이 있습니다: {numbers}")

    bonus = data["bonus_number"]
    if not isinstance(bonus, int) or not 1 <= bonus <= 45:
        raise ValueError(f"보너스 번호 범위(1~45)를 벗어났습니다: {bonus}")
    if bonus in numbers:
        raise ValueError(f"보너스 번호가 당첨번호와 중복됩니다: {bonus} in {numbers}")

    datetime.strptime(data["draw_date"], "%Y-%m-%d")  # 형식 오류 시 예외


def parse_single_lotto_draw_to_json(drw_no: int, session: requests.Session = None) -> str:
    """
    회차 데이터를 받아 검증 후 JSON 파일로 저장하고 경로를 반환합니다.
    실패하면 예외를 발생시키며, 어떤 경우에도 불완전한 파일을 남기지 않습니다.
    """
    if drw_no < 1:
        raise ValueError(f"회차 번호가 유효하지 않습니다: {drw_no}")

    session = session or build_session()
    item = fetch_draw_info(session, drw_no)
    ensure_tally_complete(item, drw_no)
    current_draw_data = build_draw_data(item, drw_no)
    validate_draw_data(current_draw_data, drw_no)

    save_dir = 'src/constant/draw_no'
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, f'{drw_no}.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(current_draw_data, f, ensure_ascii=False, indent=4)

    print(f"성공: {drw_no}회차 데이터가 '{file_path}' 파일에 저장되었습니다.")
    return file_path


def main() -> int:
    parser = argparse.ArgumentParser(description="로또 회차별 결과를 파싱하여 JSON 파일로 저장합니다.")
    parser.add_argument("drw_no", type=int, help="파싱할 로또 회차 번호 (예: 1242)")
    args = parser.parse_args()

    try:
        parse_single_lotto_draw_to_json(args.drw_no)
    except DrawNotPublished as e:
        print(f"스킵: {e}", file=sys.stderr)
        return EXIT_NOT_PUBLISHED
    except Exception as e:
        print(f"오류: {args.drw_no}회차 파싱 실패 - {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
