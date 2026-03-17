# 로또 자동 수집 시스템 (lottogo-python)

동행복권 공식 API에서 로또 6/45 당첨 정보를 자동으로 수집하고, GitHub 저장소에 JSON 파일로 저장·관리하는 자동화 시스템입니다.
GitHub Actions를 통해 **5분마다** 최신 회차를 확인하고, 새 회차가 발표되면 자동으로 데이터를 수집해 커밋·푸시합니다.

---

## 주요 특징

- **완전 자동화**: GitHub Actions 스케줄러가 5분마다 실행 — 사람이 직접 조작할 필요 없음
- **JSON API 기반**: 동행복권 사이트 개편(2026년 2월)에 대응해 HTML 스크래핑 대신 공식 JSON API 사용
- **회차별 파일 관리**: 회차마다 개별 JSON 파일로 저장 (`1215.json` 등), 1회차부터 최신까지 누적 보관
- **중복 방지**: 이미 존재하는 회차 파일이 있으면 스킵, 새 데이터만 커밋

---

## 프로젝트 구조

```
lottogo-python/
├── src/
│   ├── last_lotto_round_number.py     # 최신 회차 번호 조회
│   ├── lotto_number_parser.py         # 회차별 상세 데이터 수집
│   ├── lotto_number_parser_loop.py    # 범위 일괄 수집용 스크립트
│   └── constant/
│       ├── round_no/
│       │   └── latest_round_no.json  # 최신 회차 번호 캐시
│       └── draw_no/
│           ├── 1.json                # 1회차 데이터
│           ├── 2.json
│           ├── ...
│           └── 1215.json             # 최신 회차 데이터 (총 1,216개)
├── .github/
│   └── workflows/
│       └── auto_lotto_update.yml     # GitHub Actions 워크플로우
├── requirements.txt
└── README.md
```

---

## 사용 API

| 용도 | API URL |
|------|---------|
| 최신 회차 번호 조회 | `https://dhlottery.co.kr/selectMainInfo.do` |
| 특정 회차 상세 데이터 조회 | `https://www.dhlottery.co.kr/lt645/selectPstLt645InfoNew.do?srchDir=center&srchLtEpsd={회차}` |

두 API 모두 JSON을 반환하며, 별도 인증이 필요하지 않습니다.
`selectPstLt645InfoNew.do`는 요청 회차를 중심으로 전후 10개 회차 데이터를 반환합니다.

---

## 저장 데이터 형식

회차별 JSON 파일(`src/constant/draw_no/{회차}.json`) 예시:

```json
{
    "draw_no": 1215,
    "draw_date": "2026-03-14",
    "winning_numbers": [13, 15, 19, 21, 44, 45],
    "bonus_number": 39,
    "rank_details": [
        {
            "rank": 1,
            "total_prize_amount": 31976674128,
            "num_winners": 16,
            "prize_per_game": 1998542133,
            "winning_criteria": "당첨번호 6개 숫자일치"
        },
        {
            "rank": 2,
            "total_prize_amount": 5329445736,
            "num_winners": 76,
            "prize_per_game": 70124286,
            "winning_criteria": "당첨번호 5개 숫자일치+보너스 숫자일치"
        },
        {
            "rank": 3,
            "total_prize_amount": 5329446720,
            "num_winners": 3120,
            "prize_per_game": 1708156,
            "winning_criteria": "당첨번호 5개 숫자일치"
        },
        {
            "rank": 4,
            "total_prize_amount": 7651200000,
            "num_winners": 153024,
            "prize_per_game": 50000,
            "winning_criteria": "당첨번호 4개 숫자일치"
        },
        {
            "rank": 5,
            "total_prize_amount": 13201785000,
            "num_winners": 2640357,
            "prize_per_game": 5000,
            "winning_criteria": "당첨번호 3개 숫자일치"
        }
    ],
    "note": "",
    "misc_info": {
        "payment_deadline": "정보 없음",
        "total_sales_amount": 63488551584
    }
}
```

| 필드 | 설명 |
|------|------|
| `draw_no` | 회차 번호 |
| `draw_date` | 추첨일 (ISO 8601: `YYYY-MM-DD`) |
| `winning_numbers` | 당첨번호 6개 |
| `bonus_number` | 보너스 번호 |
| `rank_details[].rank` | 등수 (1~5) |
| `rank_details[].total_prize_amount` | 해당 등수 총 당첨금 (원) |
| `rank_details[].num_winners` | 해당 등수 당첨자 수 |
| `rank_details[].prize_per_game` | 1인당 당첨금 (원) |
| `rank_details[].winning_criteria` | 당첨 기준 설명 |
| `misc_info.total_sales_amount` | 해당 회차 총 판매금액 (원) |

---

## 스크립트 설명

### `last_lotto_round_number.py`

`selectMainInfo.do` API를 호출해 최신 회차 번호를 가져옵니다.
API가 여러 회차를 반환하므로 그 중 최댓값을 선택합니다.

```bash
python src/last_lotto_round_number.py
# 출력 예: 1215
# 저장: src/constant/round_no/latest_round_no.json
```

### `lotto_number_parser.py`

`selectPstLt645InfoNew.do` API를 호출해 지정한 회차의 상세 정보를 JSON 파일로 저장합니다.
해당 회차가 API 응답에 없을 경우 `selectMainInfo.do`에서 최신 회차 데이터로 폴백합니다.

```bash
python src/lotto_number_parser.py 1215
# 저장: src/constant/draw_no/1215.json
```

### `lotto_number_parser_loop.py`

여러 회차를 범위로 한 번에 수집할 때 사용합니다.

```bash
python src/lotto_number_parser_loop.py
```

---

## 자동화 워크플로우 (GitHub Actions)

`.github/workflows/auto_lotto_update.yml`이 다음 순서로 실행됩니다.

```
트리거: 5분마다 (cron) / main 브랜치 push / 수동 실행
          │
          ▼
1. 저장소 체크아웃
          │
          ▼
2. Python 3.11 환경 설정 + 의존성 설치
          │
          ▼
3. last_lotto_round_number.py 실행
   → 최신 회차 번호 조회 후 latest_round_no.json 저장
          │
          ▼
4. 최신 회차 JSON 파일 존재 여부 확인
   → 이미 있으면: 종료 (커밋 없음)
   → 없으면: 다음 단계 진행
          │
          ▼
5. lotto_number_parser.py {최신회차} 실행
   → 상세 데이터 수집 후 {회차}.json 저장
          │
          ▼
6. git add / commit / push
   → "Add lotto draw {회차}.json (auto-update)" 메시지로 커밋
```

---

## 로컬 실행 방법

**1. 의존성 설치**

```bash
pip install -r requirements.txt
```

**2. 최신 회차 번호 확인**

```bash
python src/last_lotto_round_number.py
```

**3. 특정 회차 데이터 수집**

```bash
python src/lotto_number_parser.py 1215
```

**4. 생성된 파일 확인**

```bash
cat src/constant/draw_no/1215.json
```

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-03-17 | 동행복권 사이트 개편 대응: HTML 스크래핑 → JSON API 전환, 누락 회차(1205~1215) 복구 |
| 초기 | HTML 스크래핑 방식으로 데이터 수집 시작 |

---

## 참고

- 동행복권 공식 사이트: [https://dhlottery.co.kr](https://dhlottery.co.kr)
- 수집 데이터는 통계 분석, 번호 패턴 연구, 앱 개발 등의 용도로 활용할 수 있습니다.
- 본 프로젝트는 동행복권의 공개 API를 사용하며, 상업적 목적의 무단 재배포는 자제해 주세요.
