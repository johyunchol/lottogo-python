import requests
import os
import json


def get_latest_lotto_round_number() -> int:
    """
    동행복권 API에서 최신 로또 회차 번호를 추출하여 반환합니다.
    (사이트 개편 후 JSON API 방식으로 변경)
    """
    url = "https://dhlottery.co.kr/selectMainInfo.do"
    try:
        response = requests.get(url)
        data = response.json()
        lt645_list = data["data"]["result"]["pstLtEpstInfo"]["lt645"]
        if lt645_list:
            return max(int(item["ltEpsd"]) for item in lt645_list)
        else:
            print("오류: API 응답에서 lt645 데이터를 찾을 수 없습니다.")
            return -1
    except requests.exceptions.RequestException as e:
        print(f"오류: 웹 페이지 요청 중 네트워크 문제 발생: {e}")
        return -1
    except Exception as e:
        print(f"오류: 최신 회차 번호 추출 중 예기치 않은 오류 발생: {e}")
        return -1


if __name__ == "__main__":
    latest_round_no = get_latest_lotto_round_number()
    print(f"{latest_round_no}")

    # 파일 저장 디렉토리 설정
    save_dir = 'src/constant/round_no'
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, f'latest_round_no.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"latest_round_no": latest_round_no}, f, ensure_ascii=False, indent=4)
        print(f"성공: {latest_round_no}회차 데이터가 '{file_path}' 파일에 저장되었습니다.")
    except Exception as e:
        print(f"오류: 파일 저장 중 예외 발생 - {e}")
