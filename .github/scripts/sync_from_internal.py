"""고객사용 사이트 ← 내부(직원용) 사이트 자동 동기화.

내부 사이트 저장소(jongkukwon-ai/halla-yn-construction-status)의 화면 파일을 그대로 복사하고,
고객사용으로 바꾸기로 한 부분만 고친다:
  - 첫 화면의 영업소 칸(부산 영업소·울산 영업소 …) 제거
  - 첫 화면 제목·탭 제목을 「고객사 전용 정보조회 시스템」으로 교체
  - 첫 화면 CI를 제목 오른쪽으로 옮기고 제목을 굵게·+2pt 크게(CUSTOMER_CSS)
  - 모든 화면(<head> 끝)에 로그인 잠금 스크립트(auth/customers.js, auth/auth.js) 연결
    (login.html·auth/ 는 고객사용 저장소에만 있고 이 스크립트가 건드리지 않는다)

  python .github/scripts/sync_from_internal.py <내부 저장소를 받은 폴더>

표준 라이브러리만 사용. 바뀐 파일 수를 출력한다.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 고객사용 저장소 맨 위
# 고객 사이트에 가져올 화면 파일(도구·문서·자동화 설정은 가져오지 않음)
FILES = ['index.html', 'manifest.json', 'sw.js', 'news-data.js',
         'news/index.html', 'construction/index.html', 'construction/soc.html', 'construction/trend.html']
DIRS = ['assets']
CUSTOMER_TITLE = '고객사 전용 정보조회 시스템'   # 첫 화면 제목·브라우저 탭 제목
# 첫 화면 모양(고객사용): CI를 제목 오른쪽으로, 제목은 굵게 + 내부 사이트보다 +2pt(≈2.7px) 크게
CUSTOMER_CSS = '''<style id="customer-hero">
    .hero-head{display:flex;flex-wrap:wrap;align-items:center;column-gap:clamp(18px,2.6vw,40px);row-gap:14px}
    .hero-title{order:1;margin-top:0;font-weight:700;font-size:clamp(30.7px,calc(3.4vw + 2.7px),48.7px)}
    .hero-ci{order:2}
  </style>
'''


def customize(rel, text):
    """고객사용으로 바꾸는 부분"""
    if rel == 'index.html':
        text, n = re.subn(r'\n[ \t]*<div class="office-chips">.*?\n[ \t]*</div>\n', '\n', text, count=1, flags=re.S)
        if n != 1:
            sys.exit('첫 화면에서 영업소 칸을 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
        for old, new in (('<div class="hero-title">영남지사 정보 조회 시스템</div>',
                          f'<div class="hero-title">{CUSTOMER_TITLE}</div>'),
                         ('<title>영남지사</title>', f'<title>{CUSTOMER_TITLE}</title>')):
            if old not in text:
                sys.exit(f'첫 화면에서 {old} 를 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
            text = text.replace(old, new, 1)
        text = text.replace('</head>', CUSTOMER_CSS + '</head>', 1)
    if rel.endswith('.html'):                              # 모든 화면에 로그인 잠금(auth/) 연결
        up = '../' * rel.count('/')
        tags = (f'<script src="{up}auth/customers.js"></script>'
                f'<script src="{up}auth/auth.js"></script>\n')
        if '</head>' not in text:
            sys.exit(f'{rel}: </head> 를 찾지 못했습니다 — 로그인 잠금을 넣을 수 없습니다.')
        text = text.replace('</head>', tags + '</head>', 1)
    return text


def main():
    src = Path(sys.argv[1]).resolve()
    if not (src / 'construction' / 'index.html').exists():
        sys.exit(f'{src}: 내부 사이트 저장소가 아닙니다.')
    changed = 0
    for rel in FILES:
        a, b = src / rel, ROOT / rel
        new = customize(rel, a.read_text(encoding='utf-8'))
        if not b.exists() or b.read_text(encoding='utf-8') != new:
            b.parent.mkdir(parents=True, exist_ok=True)
            b.write_text(new, encoding='utf-8', newline='')
            changed += 1
            print('  갱신', rel)
    for d in DIRS:
        for a in (src / d).rglob('*'):
            if a.is_file():
                b = ROOT / a.relative_to(src)
                if not b.exists() or b.read_bytes() != a.read_bytes():
                    b.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(a, b)
                    changed += 1
                    print('  갱신', b.relative_to(ROOT).as_posix())
        for b in (ROOT / d).rglob('*'):                   # 내부에서 지운 파일은 고객 사이트에서도 지움
            if b.is_file() and not (src / b.relative_to(ROOT)).exists():
                b.unlink()
                changed += 1
                print('  삭제', b.relative_to(ROOT).as_posix())
    print(f'바뀐 파일 {changed}개')


if __name__ == '__main__':
    main()
