import requests
from bs4 import BeautifulSoup

url = "https://dhlottery.co.kr/common.do?method=main"
response = requests.get(url)
response.encoding = 'euc-kr'  # 동행복권 사이트는 EUC-KR 인코딩 사용

soup = BeautifulSoup(response.text, 'html.parser')
lotto_drw_no = soup.find('strong', id='lottoDrwNo')

if lotto_drw_no:
    print(lotto_drw_no.text.strip())
else:
    print("lottoDrwNo 태그를 찾을 수 없습니다.")
