import json
import os
import sys
from datetime import datetime, timedelta, timezone

# 로또 6/45 1회차 추첨일: 2002-12-07(토). 이후 매주 토요일 1회씩 시행된다.
# 추첨 방송은 20:35경 시작하고 당첨번호가 사이트에 반영되기까지 시차가 있으므로,
# 새 회차로 넘어가는 경계를 21:00 KST로 둔다.
KST = timezone(timedelta(hours=9))
FIRST_DRAW_AT = datetime(2002, 12, 7, 21, 0, tzinfo=KST)
DRAW_INTERVAL = timedelta(weeks=1)


def get_latest_lotto_round_number(now: datetime = None) -> int:
    """
    추첨 일정으로 최신(게시 완료된) 회차 번호를 계산합니다.

    동행복권 사이트를 호출하지 않으므로 사이트 점검/차단/개편의 영향을 받지 않습니다.
    계산이 불가능한 상황(시스템 시각 이상)에서는 예외를 발생시킵니다.
    """
    if now is None:
        now = datetime.now(KST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=KST)

    round_no = (now - FIRST_DRAW_AT) // DRAW_INTERVAL + 1
    if round_no < 1:
        raise ValueError(f"계산된 회차 번호가 비정상입니다: {round_no} (기준 시각: {now.isoformat()})")
    return round_no


def main() -> int:
    try:
        latest_round_no = get_latest_lotto_round_number()
    except Exception as e:
        print(f"오류: 최신 회차 번호 계산 실패 - {e}", file=sys.stderr)
        return 1

    print(f"{latest_round_no}")

    save_dir = 'src/constant/round_no'
    os.makedirs(save_dir, exist_ok=True)

    file_path = os.path.join(save_dir, 'latest_round_no.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({"latest_round_no": latest_round_no}, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"오류: 파일 저장 중 예외 발생 - {e}", file=sys.stderr)
        return 1

    print(f"성공: {latest_round_no}회차 번호가 '{file_path}' 파일에 저장되었습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
