import psycopg2
from store_data_in_database import db_params


def get_pass_datetime(serial):
    conn = psycopg2.connect(**db_params)
    try:
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT scanned_at
                   FROM genesis_records
                   WHERE serial = %s AND result = 'OK'
                   ORDER BY scanned_at DESC
                   LIMIT 1''',
                (serial,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


if __name__ == '__main__':
    dt = get_pass_datetime('8B26Y0800670200')
    if dt:
        print('ผ่าน OK เมื่อ', dt.strftime('%d/%m/%Y %H:%M'))   # ผ่าน OK เมื่อ 16/11/2026 18:43
    else:
        print('ไม่พบ (ยังไม่ผ่าน หรือยังไม่ถูกเก็บลง DB)')