"""고객사 로그인용 판매처 코드 목록(auth/customers.js) 만들기.

  py auth/tools/make_customers.py <엑셀(.xlsx) 또는 CSV> [--out auth/customers.js] [--csv-out 목록.local.csv]

입력 파일에서 '판매처 코드'·'판매처 명' 두 열을 찾아(엑셀은 모든 시트의 첫 5줄 안에서 제목줄 탐색)
고객사 목록을 만든다. CSV는 첫 줄이 제목이고 '판매처 코드','판매처 명' 열이 있어야 한다.

저장소(공개)에는 코드·업체명 원문을 올리지 않는다.
  - 코드  → PBKDF2-SHA256(20만 회)으로 늘린 값의 앞 16바이트(조회용 번호)
  - 업체명 → 같은 값의 뒤 32바이트를 키로 AES-256-GCM 암호화 (코드를 입력해야만 풀림)
코드 원문과 업체명은 customers.js에 남지 않는다. 로그인 화면(auth/auth.js)과 계산 방식이 같아야 하므로
salt·반복 횟수는 customers.js 머리말에 같이 적어 두고, 다시 만들 때는 기존 값을 그대로 쓴다
(바꾸면 이미 로그인한 고객이 모두 풀린다).

목록에서 빠진 코드는 다음 접속 때 자동 로그아웃된다. 목록을 손보려면 --csv-out 으로 뽑아 고친 뒤 다시 입력으로 쓰면 된다
(.local.csv 로 끝나는 파일은 .gitignore 로 저장소에서 제외된다).
"""
import argparse
import base64
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ITER = 200_000
CODE_COL, NAME_COL = '판매처 코드', '판매처 명'


def normalize(code):
    """auth.js의 normalize()와 같아야 한다: 공백 제거 + 대문자"""
    return re.sub(r'\s+', '', str(code)).upper()


def derive(code, salt):
    dk = hashlib.pbkdf2_hmac('sha256', normalize(code).encode('utf-8'), salt, ITER, 64)
    return dk[:16].hex(), dk[32:]          # (조회 번호, AES 키)


def read_pairs(path):
    pairs = {}

    def add(code, name):
        if code is None or name is None:
            return
        code = normalize(int(code) if isinstance(code, float) and code == int(code) else code)
        name = str(name).strip()
        if code and name and code not in pairs:
            pairs[code] = name

    if path.suffix.lower() == '.csv':
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                add(row.get(CODE_COL), row.get(NAME_COL))
    else:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            hdr = None
            for i, r in enumerate(rows):
                if i >= 5:
                    break
                if r and CODE_COL in r and NAME_COL in r:
                    hdr = list(r)
                    break
            if hdr is None:
                continue
            ci, ni = hdr.index(CODE_COL), hdr.index(NAME_COL)
            for r in rows:                      # 제목줄 다음부터 이어서 읽는다
                add(r[ci], r[ni])
    return pairs


def load_existing(out):
    if not out.exists():
        return None
    m = re.search(r'=\s*(\{.*\})\s*;?\s*$', out.read_text(encoding='utf-8'), re.S)
    return json.loads(m.group(1)) if m else None


def decrypt_name(entry, key):
    try:
        ct = AESGCM(key).decrypt(base64.b64decode(entry['v']), base64.b64decode(entry['c']), None)
        return ct.decode('utf-8')
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('source', type=Path)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'customers.js')
    ap.add_argument('--csv-out', type=Path, help='읽은 목록을 CSV로도 저장(고쳐서 다시 입력으로 사용 가능)')
    a = ap.parse_args()

    pairs = read_pairs(a.source)
    if not pairs:
        sys.exit(f"'{CODE_COL}'·'{NAME_COL}' 열을 가진 행을 찾지 못했습니다: {a.source}")

    old = load_existing(a.out)
    salt_b64 = old['salt'] if old else base64.b64encode(os.urandom(16)).decode()
    if old and old.get('iter') != ITER:
        sys.exit('기존 customers.js의 반복 횟수가 달라 새로 만들 수 없습니다 — 파일을 지우고 다시 만들면 모든 고객이 다시 로그인해야 합니다.')
    salt = base64.b64decode(salt_b64)
    prev = {e['i']: e for e in (old['list'] if old else [])}

    out_list, reused = [], 0
    for code, name in sorted(pairs.items()):
        idx, key = derive(code, salt)
        e = prev.get(idx)
        if e and decrypt_name(e, key) == name:        # 바뀐 게 없으면 암호문도 그대로 → 깃 기록이 조용함
            reused += 1
        else:
            iv = os.urandom(12)
            e = {'i': idx, 'v': base64.b64encode(iv).decode(),
                 'c': base64.b64encode(AESGCM(key).encrypt(iv, name.encode('utf-8'), None)).decode()}
        out_list.append(e)

    out_list.sort(key=lambda e: e['i'])               # 코드 순서가 드러나지 않게 정렬
    data = {'v': 1, 'iter': ITER, 'salt': salt_b64, 'list': out_list}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text('/* 고객사 판매처 코드 목록 — auth/tools/make_customers.py 로 생성(직접 고치지 말 것) */\n'
                     'window.HALLA_CUSTOMERS = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';\n',
                     encoding='utf-8', newline='\n')

    for code, name in pairs.items():                  # 만든 파일이 실제로 풀리는지 확인
        idx, key = derive(code, salt)
        e = next(x for x in out_list if x['i'] == idx)
        assert decrypt_name(e, key) == name, f'검증 실패: {code}'

    if a.csv_out:
        with open(a.csv_out, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow([CODE_COL, NAME_COL])
            w.writerows(sorted(pairs.items()))
    print(f'고객사 {len(pairs)}곳 → {a.out} (기존 항목 재사용 {reused}, 새로 만듦 {len(pairs) - reused})')


if __name__ == '__main__':
    main()
