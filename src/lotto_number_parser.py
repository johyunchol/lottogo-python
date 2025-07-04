import argparse
import json
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

def clean_note_text(text: str) -> str:
    cleaned = re.sub(r'[\r\n\t]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def parse_korean_date_to_iso(date_str: str) -> str:
    """
    '2024년 06월 01일' -> '2024-06-01'로 변환
    """
    try:
        # 공백 제거
        date_str = date_str.strip()
        # '년', '월', '일' 제거 및 '-'로 변환
        dt = datetime.strptime(date_str, "%Y년 %m월 %d일")
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        # 변환 실패 시 원본 반환
        return date_str

def parse_single_lotto_draw_to_json(drw_no):
    url = f"https://dhlottery.co.kr/gameResult.do?method=byWin&drwNo={drw_no}"
    current_draw_data = {
        "draw_no": drw_no,
        "draw_date": None,  # 날짜는 ISO 포맷 문자열로 저장
        "winning_numbers": [],
        "bonus_number": 0,
        "rank_details": [],
        "note": "",
        "misc_info": {
            "payment_deadline": "정보 없음",
            "total_sales_amount": 0
        }
    }

    try:
        response = requests.get(url)
        response.encoding = 'euc-kr'
        soup = BeautifulSoup(response.text, 'html.parser')

        win_result_div = soup.find('div', class_='win_result')
        date_str = None
        if win_result_div:
            # 회차 날짜
            drw_info_h4 = win_result_div.find('h4')
            if drw_info_h4:
                drw_text = drw_info_h4.text.strip()
                if '(' in drw_text and '추첨)' in drw_text:
                    date_match = drw_text.split('(')[-1].replace('추첨)', '').strip()
                    date_str = date_match

            desc_p = win_result_div.find('p', class_='desc')
            if desc_p:
                date_text = desc_p.text.strip()
                if '추첨)' in date_text:
                    date_str = date_text.replace('(', '').replace(' 추첨)', '').strip()

            # 날짜를 ISO 포맷으로 변환
            if date_str:
                current_draw_data["draw_date"] = parse_korean_date_to_iso(date_str)
            else:
                current_draw_data["draw_date"] = None

            # 당첨번호
            win_num_div = win_result_div.find('div', class_='num win')
            if win_num_div:
                winning_balls_str = [ball.text.strip() for ball in win_num_div.select('span.ball_645')]
                current_draw_data["winning_numbers"] = [int(num) for num in winning_balls_str if num.isdigit()]

            # 보너스번호
            bonus_num_div = win_result_div.find('div', class_='num bonus')
            if bonus_num_div:
                bonus_ball = bonus_num_div.select_one('span.ball_645')
                if bonus_ball and bonus_ball.text.strip().isdigit():
                    current_draw_data["bonus_number"] = int(bonus_ball.text.strip())

            # 등수별 당첨 정보
            detail_table = soup.find('table', class_='tbl_data tbl_data_col')
            notes_list = []
            if detail_table:
                rows = detail_table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        rank_str = cols[0].text.strip()
                        rank_num = int(rank_str.replace('등', '')) if '등' in rank_str and rank_str.replace('등', '').isdigit() else 0
                        num_winners_str = cols[2].text.strip().replace(',', '')
                        num_winners_int = int(num_winners_str) if num_winners_str.isdigit() else 0
                        total_prize_amount_str = cols[1].text.strip().replace(',', '').replace('원', '')
                        total_prize_amount_val = int(total_prize_amount_str) if total_prize_amount_str.isdigit() else 0
                        prize_per_game_str = cols[3].text.strip().replace(',', '').replace('원', '')
                        prize_per_game_val = int(prize_per_game_str) if prize_per_game_str.isdigit() else 0
                        note_val = cols[5].text.strip() if len(cols) > 5 else ''
                        if note_val:
                            notes_list.append(note_val)
                        rank_detail = {
                            'rank': rank_num,
                            'total_prize_amount': total_prize_amount_val,
                            'num_winners': num_winners_int,
                            'prize_per_game': prize_per_game_val,
                            'winning_criteria': cols[4].text.strip()
                        }
                        current_draw_data["rank_details"].append(rank_detail)
                joined_notes = " / ".join(notes_list) if notes_list else ""
                current_draw_data["note"] = clean_note_text(joined_notes)

            # 기타 정보
            misc_info_ul = soup.find('ul', class_='list_text_common')
            if misc_info_ul:
                list_items = misc_info_ul.find_all('li')
                for li in list_items:
                    li_text = li.text.strip()
                    if '당첨금 지급기한' in li_text:
                        current_draw_data["misc_info"]["payment_deadline"] = li_text.replace('당첨금 지급기한 :', '').strip()
                    elif '총판매금액' in li_text:
                        strong_tag = li.find('strong')
                        if strong_tag:
                            total_sales_str = strong_tag.text.strip().replace(',', '').replace('원', '')
                            current_draw_data["misc_info"]["total_sales_amount"] = int(total_sales_str) if total_sales_str.isdigit() else 0
                        else:
                            total_sales_str = li_text.replace('총판매금액 :', '').strip().replace(',', '').replace('원', '')
                            current_draw_data["misc_info"]["total_sales_amount"] = int(total_sales_str) if total_sales_str.isdigit() else 0

    except Exception as e:
        print(f"오류: 파싱 중 예외 발생 - {e}")

    # 파일 저장 디렉토리 설정
    save_dir = 'src/constant/draw_no'
    os.makedirs(save_dir, exist_ok=True)  # 폴더 없으면 생성

    file_path = os.path.join(save_dir, f'{drw_no}.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(current_draw_data, f, ensure_ascii=False, indent=4)
        print(f"성공: {drw_no}회차 데이터가 '{file_path}' 파일에 저장되었습니다.")
    except Exception as e:
        print(f"오류: 파일 저장 중 예외 발생 - {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="로또 회차별 결과를 파싱하여 JSON 파일로 저장합니다.")
    parser.add_argument("drw_no", type=int, help="파싱할 로또 회차 번호 (예: 1135)")
    args = parser.parse_args()

    parse_single_lotto_draw_to_json(args.drw_no)
