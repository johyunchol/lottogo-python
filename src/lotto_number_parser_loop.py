from lotto_number_parser import parse_single_lotto_draw_to_json
from last_lotto_round_number import get_latest_lotto_round_number  # 최신 회차 번호 가져오는 함수

def main():
    latest_round = get_latest_lotto_round_number()
    if latest_round == -1:
        print("최신 회차 번호를 가져오지 못했습니다. 종료합니다.")
        return

    print(f"1부터 {latest_round}회차까지 파싱을 시작합니다.")
    for drw_no in range(1, latest_round + 1):
        print(f"{drw_no}회차 파싱 중...")
        parse_single_lotto_draw_to_json(drw_no)
    print("모든 회차 파싱 완료.")

if __name__ == "__main__":
    main()
