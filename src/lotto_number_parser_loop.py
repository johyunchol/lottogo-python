import os
import sys
import time

from lotto_number_parser import (
    DrawNotPublished,
    build_session,
    parse_single_lotto_draw_to_json,
)
from last_lotto_round_number import get_latest_lotto_round_number

REQUEST_INTERVAL = 0.3  # 초. 전 회차 순회 시 동행복권에 과부하를 주지 않도록 간격을 둔다.


def main() -> int:
    try:
        latest_round = get_latest_lotto_round_number()
    except Exception as e:
        print(f"오류: 최신 회차 번호 계산 실패 - {e}", file=sys.stderr)
        return 1

    print(f"1부터 {latest_round}회차까지 파싱을 시작합니다.")
    session = build_session()
    skipped, failed = [], []

    for drw_no in range(1, latest_round + 1):
        # 이미 받아둔 회차는 건너뛴다 (재실행 시 불필요한 요청 방지).
        if os.path.exists(os.path.join('src/constant/draw_no', f'{drw_no}.json')):
            continue

        print(f"{drw_no}회차 파싱 중...")
        try:
            parse_single_lotto_draw_to_json(drw_no, session=session)
        except DrawNotPublished as e:
            print(f"  스킵: {e}", file=sys.stderr)
            skipped.append(drw_no)
        except Exception as e:
            # 한 회차 실패로 전체 순회를 중단하지 않되, 실패는 반드시 기록하고 종료코드에 반영한다.
            print(f"  실패: {type(e).__name__}: {e}", file=sys.stderr)
            failed.append(drw_no)
        time.sleep(REQUEST_INTERVAL)

    print(f"완료. 스킵 {len(skipped)}건, 실패 {len(failed)}건.")
    if failed:
        print(f"실패한 회차: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
