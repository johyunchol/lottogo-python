import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY 환경변수가 설정되지 않았습니다.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_table_data(table_name: str):
    response = supabase.table(table_name).select("*").execute()
    print("Raw response:", response)
    data = response.data
    if not data:
        print(f"'{table_name}' 테이블에서 데이터를 불러올 수 없습니다.")
    return data

def insert_table_data(table_name: str, row: dict):
    response = supabase.table(table_name).insert(row).execute()
    print("Insert response:", response)
    data = response.data
    if not data:
        print(f"'{table_name}' 테이블에 데이터 추가에 실패했습니다.")
    return data

if __name__ == "__main__":
    print(get_table_data("lottos"))

    # 예시 데이터 insert
    row = {
        "round": 123,
        "note": "테스트",
        "payment_deadline": "지급기한",
        "total_sales_amount": 1000000,
        "draw_date": "2023-10-01T00:00:00Z",
    }
    print(insert_table_data("lottos", row))
