import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

from lotto_number_parser import build_session, round_exists

# 로또 6/45 1회차 추첨일: 2002-12-07(토). 이후 매주 토요일 1회씩 시행된다.
# 추첨 방송은 20:35경 시작하고 당첨번호가 사이트에 반영되기까지 시차가 있으므로,
# 새 회차 후보로 넘어가는 경계를 21:00 KST로 둔다.
KST = timezone(timedelta(hours=9))
FIRST_DRAW_AT = datetime(2002, 12, 7, 21, 0, tzinfo=KST)
DRAW_INTERVAL = timedelta(weeks=1)

# 방송 편성이 밀려 게시가 늦어지는 경우를 흡수하는 허용 범위(회차 수).
# 예) 2026-09-26(1243회)는 아시안게임 중계로 22:30 이후 방송되어,
#     21:00~22:40 사이에는 계산값이 1243인데 API에는 1242까지만 있었다.
# 2회차(2주) 이상 벌어지면 추첨 일정 자체가 어긋난 것으로 보고 실패시킨다.
MAX_ROUND_LAG = 1


def calculate_round_from_date(now: datetime = None) -> int:
    """
    추첨 일정으로 '이 시점에 나와 있어야 할' 회차 번호를 계산합니다. 네트워크를 쓰지 않습니다.
    실제로 게시됐는지는 보장하지 않으므로 resolve_latest_round()로 확정해야 합니다.
    """
    if now is None:
        now = datetime.now(KST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=KST)

    round_no = (now - FIRST_DRAW_AT) // DRAW_INTERVAL + 1
    if round_no < 1:
        raise ValueError(f"계산된 회차 번호가 비정상입니다: {round_no} (기준 시각: {now.isoformat()})")
    return round_no


def resolve_latest_round(session: requests.Session = None, now: datetime = None) -> int:
    """
    날짜로 후보를 잡고, 동행복권에 실제로 게시된 최신 회차를 확정합니다.

    방송이 늦어지면 계산값은 이미 다음 회차를 가리키지만 API에는 아직 없다.
    이때는 한 회차씩 내려가며 실제 게시된 회차를 찾는다. 계산값과 MAX_ROUND_LAG를
    넘게 벌어지면 추첨 일정이 어긋났거나 API가 이상한 것이므로 예외를 발생시킨다.
    """
    candidate = calculate_round_from_date(now)
    session = session or build_session()

    for lag in range(MAX_ROUND_LAG + 1):
        drw_no = candidate - lag
        if drw_no < 1:
            break
        if round_exists(session, drw_no):
            if lag:
                print(
                    f"알림: 계산상 {candidate}회차지만 아직 게시되지 않아 {drw_no}회차를 최신으로 봅니다. "
                    f"(추첨/방송 지연 가능)"
                )
            return drw_no

    raise ValueError(
        f"게시된 최신 회차를 확인할 수 없습니다. "
        f"{candidate}회차부터 {max(candidate - MAX_ROUND_LAG, 1)}회차까지 조회했으나 모두 없었습니다. "
        f"추첨 일정이 어긋났거나 동행복권 API가 이상할 수 있습니다."
    )


# 기존 호출부 호환용 이름.
def get_latest_lotto_round_number(session: requests.Session = None) -> int:
    return resolve_latest_round(session)


def main() -> int:
    try:
        latest_round_no = resolve_latest_round()
    except Exception as e:
        print(f"오류: 최신 회차 확정 실패 - {type(e).__name__}: {e}", file=sys.stderr)
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
