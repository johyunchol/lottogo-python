import argparse
import json
import os
from datetime import datetime

import requests


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


def parse_date(ymd: str) -> str:
    """'20260307' -> '2026-03-07'"""
    try:
        return datetime.strptime(ymd, "%Y%m%d").strftime("%Y-%m-%d")
    except Exception:
        return ymd


def fetch_draw_info(drw_no: int) -> dict:
    """
    selectPstLt645InfoNew.do API에서 특정 회차 데이터를 반환합니다.
    요청 회차를 중심으로 10개 회차를 반환하므로 정확한 회차를 찾아 반환합니다.
    없으면 selectMainInfo.do에서 최신 회차를 반환합니다.
    """
    url = (
        f"https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do"
        f"?srchDir=center&srchLtEpsd={drw_no}"
    )
    response = requests.get(url, headers=HEADERS, timeout=10)
    data = response.json()
    lt645_list = data.get("data", {}).get("list", [])

    for item in lt645_list:
        if int(item["ltEpsd"]) == drw_no:
            return item

    # 해당 회차가 목록에 없으면 selectMainInfo.do에서 최신 회차로 폴백
    print(f"경고: 회차({drw_no})를 찾을 수 없습니다. selectMainInfo.do에서 최신 회차를 사용합니다.")
    fallback_url = "https://dhlottery.co.kr/selectMainInfo.do"
    fb_response = requests.get(fallback_url, timeout=10)
    fb_data = fb_response.json()
    lt645_fallback = fb_data["data"]["result"]["pstLtEpstInfo"]["lt645"]
    if not lt645_fallback:
        raise ValueError("API 응답에서 데이터를 찾을 수 없습니다.")
    return max(lt645_fallback, key=lambda x: int(x["ltEpsd"]))


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
        "draw_date": parse_date(item.get("ltRflYmd", "")),
        "winning_numbers": [
            item["tm1WnNo"], item["tm2WnNo"], item["tm3WnNo"],
            item["tm4WnNo"], item["tm5WnNo"], item["tm6WnNo"],
        ],
        "bonus_number": item["bnsWnNo"],
        "rank_details": rank_details,
        "note": "",
        "misc_info": {
            "payment_deadline": "정보 없음",
            "total_sales_amount": item.get("rlvtEpsdSumNtslAmt", 0),
        },
    }


def parse_single_lotto_draw_to_json(drw_no: int):
    try:
        item = fetch_draw_info(drw_no)
        current_draw_data = build_draw_data(item, drw_no)
    except Exception as e:
        print(f"오류: 파싱 중 예외 발생 - {e}")
        current_draw_data = {
            "draw_no": drw_no,
            "draw_date": None,
            "winning_numbers": [],
            "bonus_number": 0,
            "rank_details": [],
            "note": "",
            "misc_info": {"payment_deadline": "정보 없음", "total_sales_amount": 0},
        }

    save_dir = 'src/constant/draw_no'
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, f'{drw_no}.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(current_draw_data, f, ensure_ascii=False, indent=4)
        print(f"성공: {drw_no}회차 데이터가 '{file_path}' 파일에 저장되었습니다.")
    except Exception as e:
        print(f"오류: 파일 저장 중 예외 발생 - {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="로또 회차별 결과를 파싱하여 JSON 파일로 저장합니다.")
    parser.add_argument("drw_no", type=int, help="파싱할 로또 회차 번호 (예: 1215)")
    args = parser.parse_args()

    parse_single_lotto_draw_to_json(args.drw_no)
