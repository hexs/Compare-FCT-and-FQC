import csv
import io
import logging
import os
import re
import time
from datetime import datetime

import psycopg2
import requests

# ---------------- Config ----------------
HOSTS = [
    '10.87.1.224:2001',
    '10.87.1.225:2001',
]
SUBFOLDERS = ['Passed']
MIN_YEAR = 2026
INTERVAL = 60  # วินาที
DEVICE_PREFIX = 'Genesis_ALPHA_'

db_params = {
    'dbname': 'test',
    'user': 'postgres',
    'password': os.environ.get('POSTGRES_PASSWORD'),
    'host': '10.87.1.231',
    'port': '5432'
}

MONTH_RE = re.compile(r'^(\d{2})-(\d{4})$')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('genesis')


# ---------------- HTTP helpers ----------------
def list_dir(host, path):
    r = requests.get(f'http://{host}/api/iterdir', params={'p': path}, timeout=15)
    r.raise_for_status()
    return r.json()['children']


def read_text(host, path):
    r = requests.get(f'http://{host}/file', params={'p': path}, timeout=30)
    r.raise_for_status()
    return r.content.decode('utf-8-sig', errors='replace')


# ---------------- DB ----------------
def init_db(conn):
    with conn.cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS genesis_records (
                id SERIAL PRIMARY KEY,
                device VARCHAR(100) NOT NULL,
                serial VARCHAR(100) NOT NULL,
                result VARCHAR(10),
                scanned_at TIMESTAMP NOT NULL,
                source_file TEXT,
                UNIQUE (device, serial, scanned_at)
            );
            CREATE TABLE IF NOT EXISTS genesis_file_state (
                path TEXT PRIMARY KEY,
                size BIGINT NOT NULL,
                updated_at TIMESTAMP DEFAULT now()
            );
        ''')
    conn.commit()


def load_state(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT path, size FROM genesis_file_state')
        return dict(cur.fetchall())


# ---------------- CSV ----------------
def parse_dt(s):
    s = s.strip()
    for fmt in ('%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M',
                '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
                '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def parse_csv(text):
    lines = text.splitlines()
    if not lines:
        return []
    first = lines[0]
    delim = '\t' if first.count('\t') > first.count(',') else ','

    reader = csv.reader(io.StringIO(text), delimiter=delim)
    header = [h.strip() for h in next(reader, [])]
    try:
        i_dt = header.index('DateTime')
        i_sn = header.index('Serial')
    except ValueError:
        # raise เพื่อไม่ให้บันทึก size ไฟล์นี้ จะได้ลองใหม่รอบหน้า
        raise ValueError(f'ไม่พบคอลัมน์ DateTime/Serial header={header[:8]}')
    i_res = header.index('OK/NG') if 'OK/NG' in header else None

    rows = []
    for row in reader:
        if len(row) <= max(i_dt, i_sn):
            continue
        dt = parse_dt(row[i_dt])
        serial = row[i_sn].strip()
        if dt is None or not serial or dt.year < MIN_YEAR:
            continue
        result = row[i_res].strip() if i_res is not None and i_res < len(row) else ''
        rows.append((serial, result, dt))
    return rows


def describe_first_row(text):
    """ใช้แสดงในข้อความ error เพื่อดูว่าทำไมแปลงแถวไม่ได้"""
    lines = text.splitlines()
    if len(lines) < 2:
        return '(ไม่มีแถวข้อมูล)'
    first = lines[0]
    delim = '\t' if first.count('\t') > first.count(',') else ','
    header = [h.strip() for h in first.split(delim)]
    row = next(csv.reader([lines[1]], delimiter=delim), [])
    try:
        i_dt = header.index('DateTime')
        i_sn = header.index('Serial')
        if len(row) > max(i_dt, i_sn):
            return f'ช่อง={len(row)} DateTime={row[i_dt]!r} Serial={row[i_sn]!r}'
        return f'แถวสั้นเกิน ช่อง={len(row)}'
    except ValueError:
        return f'header={header[:8]}'


# ---------------- Core ----------------
def scan_host(conn, host, state):
    """สแกน 1 เครื่อง คืนจำนวนไฟล์ที่อ่านสำเร็จ"""
    changed = 0
    devices = [c['name'] for c in list_dir(host, 'C:/')
               if c['name'].startswith(DEVICE_PREFIX)]

    for dev in devices:
        try:
            months = list_dir(host, f'C:/{dev}/log')
        except Exception as e:
            log.warning('[%s] %s: อ่าน log ไม่ได้: %s', host, dev, e)
            continue

        for m in months:
            mt = MONTH_RE.match(m['name'])
            if not mt or int(mt.group(2)) < MIN_YEAR:
                continue

            for sub in SUBFOLDERS:
                folder = f'C:/{dev}/log/{m["name"]}/{sub}'
                try:
                    files = list_dir(host, folder)
                except Exception:
                    continue  # ไม่มีโฟลเดอร์นี้

                for f in files:
                    if not f['name'].lower().endswith('.csv'):
                        continue
                    path = f'{folder}/{f["name"]}'
                    key = f'{host}|{path}'  # แยกสถานะตามเครื่อง
                    size = f['size']
                    if state.get(key) == size:
                        continue  # size ไม่เปลี่ยน

                    try:
                        text = read_text(host, path)
                        rows = parse_csv(text)
                        if not rows and len(text.splitlines()) > 1:
                            raise ValueError('มีข้อมูลแต่แปลงได้ 0 แถว | ' + describe_first_row(text))

                        with conn.cursor() as cur:
                            for serial, result, dt in rows:
                                cur.execute(
                                    '''INSERT INTO genesis_records
                                           (device, serial, result, scanned_at, source_file)
                                       VALUES (%s, %s, %s, %s,
                                               %s) ON CONFLICT (device, serial, scanned_at) DO NOTHING''',
                                    (dev, serial, result, dt, key))
                            cur.execute(
                                '''INSERT INTO genesis_file_state (path, size)
                                   VALUES (%s, %s) ON CONFLICT (path) DO
                                UPDATE
                                    SET size = EXCLUDED.size, updated_at = now()''',
                                (key, size))
                        conn.commit()
                        state[key] = size
                        changed += 1
                        log.info('[%s] %s: อ่าน %d แถว (size %s)', host, path, len(rows), size)
                    except Exception as e:
                        conn.rollback()
                        log.error('[%s] %s: ผิดพลาด: %s', host, path, e)
    return changed


def scan_once(conn):
    t0 = time.time()
    state = load_state(conn)
    total = 0
    for host in HOSTS:
        try:
            total += scan_host(conn, host, state)
        except psycopg2.Error:
            raise  # ให้ main() เชื่อมต่อ DB ใหม่
        except Exception as e:
            # เครื่องใดเครื่องหนึ่งล่ม ไม่ให้กระทบอีกเครื่อง
            log.error('[%s] เชื่อมต่อ/สแกนไม่สำเร็จ: %s', host, e)

    log.info('สแกนเสร็จ: ไฟล์ที่เปลี่ยน %d ไฟล์ ใช้เวลา %.1f วินาที', total, time.time() - t0)


def main():
    conn = psycopg2.connect(**db_params)
    init_db(conn)
    log.info('เริ่มทำงาน %d เครื่อง ตรวจทุก %d วินาที', len(HOSTS), INTERVAL)
    while True:
        start = time.time()
        try:
            scan_once(conn)
        except psycopg2.Error as e:
            log.error('DB error: %s — เชื่อมต่อใหม่', e)
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(5)
            conn = psycopg2.connect(**db_params)
        except Exception as e:
            log.error('scan ผิดพลาด: %s', e)
        time.sleep(max(1, INTERVAL - (time.time() - start)))


if __name__ == '__main__':
    main()
