"""고객사용 사이트 ← 내부(직원용) 사이트 자동 동기화.

내부 사이트 저장소(jongkukwon-ai/halla-yn-construction-status)의 화면 파일을 그대로 복사하고,
고객사용으로 바꾸기로 한 부분만 고친다:
  - 첫 화면의 영업소 칸(부산 영업소·울산 영업소 …) 제거
  - 첫 화면 제목·탭 제목을 「건설 정보 조회 시스템 (고객사용)」으로 교체
  - 첫 화면 메뉴 카드 3개에 간략한 설명 문구 추가(NAV_DESC)
  - 각 정보 화면 왼쪽 위 「← 영남지사」 버튼을 「🏠 돌아가기」로 교체
  - 첫 화면 제목을 굵게·+2pt 크게, 제목 아래에 「고객사 : 업체명」 자리 추가(CUSTOMER_CSS)
  - 모든 화면(<head> 끝)에 로그인 잠금 스크립트(auth/customers.js, auth/auth.js) 연결 — 주소 뒤에 ?v=내용지문을 붙여
    스크립트를 고치면 방문자 브라우저가 옛 파일을 쓰지 않게 한다(login.html 도 같이 갱신)
    (login.html·auth/ 는 고객사용 저장소에만 있고 이 스크립트가 건드리지 않는다)

  python .github/scripts/sync_from_internal.py <내부 저장소를 받은 폴더>

표준 라이브러리만 사용. 바뀐 파일 수를 출력한다.
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 고객사용 저장소 맨 위
# 고객 사이트에 가져올 화면 파일(도구·문서·자동화 설정은 가져오지 않음)
FILES = ['index.html', 'manifest.json', 'sw.js', 'news-data.js',
         'news/index.html', 'construction/index.html', 'construction/soc.html', 'construction/trend.html']
DIRS = ['assets']
CUSTOMER_TITLE = '건설 정보 조회 시스템 (고객사용)'   # 첫 화면 제목·브라우저 탭 제목
BACK_PAGES = ['construction/index.html', 'construction/trend.html', 'news/index.html']   # 「← 영남지사」 버튼이 있는 화면
# 첫 화면 메뉴 카드 3개의 간략한 설명(내부 사이트에선 빼 두었지만 고객사용엔 다시 넣는다)
NAV_DESC = {
    '영남지역 착공현황': '부산·울산·경남·경북·대구 아파트/SOC 착공 현장을 지역·상태·건설사별로 조회합니다.',
    '업종 관련 뉴스': '영남지역 건설 소식과 레미콘·시멘트 업계 뉴스를 최신순으로 모아봅니다. 검색으로 다른 기사도 찾을 수 있습니다.',
    '영남권 착공·인허가 통계': '국토교통부 통계누리 자료로 부산·울산·대구·경남·경북의 건축 착공·인허가 연면적·동수 추이를 확인합니다.',
}
# 첫 화면 모양(고객사용): 제목은 굵게 + 내부 사이트보다 +2pt(≈2.7px) 크게 (CI 위치는 내부 사이트 그대로),
# 제목 아래 「고객사 : 업체명」(업체명은 auth/auth.js가 로그인 정보로 채움).
# 시작 위치는 제목의 「정보」 글자 아래 — 제목 앞부분(「건설 」)과 같은 글꼴·크기의 투명 글자로 폭을 맞춘다(화면 폭이 달라져도 따라감).
TITLE_PAD = CUSTOMER_TITLE.split('정보')[0]
CUSTOMER_CSS = '''<style id="customer-hero">
    .hero-title{font-weight:700;font-size:clamp(30.7px,calc(3.4vw + 2.7px),48.7px)}
    .hero-greeting{display:flex;align-items:flex-start;margin-top:clamp(10px,1.8vh,18px);
      font-size:clamp(17px,1.7vw,24px);line-height:1.4;
      color:rgba(255,255,255,0.72);word-break:keep-all;animation:greet-in .6s ease-out both}
    .nav-card-desc{flex:1 0 auto;max-width:32em;margin-top:10px;font-size:clamp(13px,1.05vw,15px);line-height:1.6;word-break:keep-all}
    .hero-greeting[hidden]{display:none}
    .hero-greeting-pad{flex:none;height:0;overflow:hidden;visibility:hidden;white-space:pre;
      font-weight:700;font-size:clamp(30.7px,calc(3.4vw + 2.7px),48.7px);letter-spacing:-.01em}
    .hero-greeting strong{margin-left:.4em;font-weight:700;font-size:clamp(18.3px,calc(1.7vw + 1.3px),25.3px);color:#A6DD62}
    @keyframes greet-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
    @media(prefers-reduced-motion:reduce){.hero-greeting{animation:none}}
  </style>
'''


def auth_version(name):
    """auth/ 안 스크립트의 내용 지문(앞 8자리). 주소 뒤에 ?v=지문 으로 붙여, 스크립트를 고치면 브라우저가 옛 파일(GitHub Pages는 10분간 캐시)을 쓰지 않고 바로 새로 받게 한다."""
    data = (ROOT / 'auth' / name).read_bytes().replace(b'\r\n', b'\n')     # 줄바꿈 차이로 지문이 흔들리지 않게
    return hashlib.sha1(data).hexdigest()[:8]


def stamp_login():
    """login.html(동기화 대상이 아닌 고객사용 전용 파일)의 auth 스크립트 주소에도 같은 지문을 붙인다. 바뀌었으면 True"""
    f = ROOT / 'login.html'
    old = f.read_text(encoding='utf-8')
    new = re.sub(r'(src="\./auth/(auth|customers)\.js)(\?v=[0-9a-f]+)?"',
                 lambda m: f'{m.group(1)}?v={auth_version(m.group(2) + ".js")}"', old)
    if new != old:
        f.write_text(new, encoding='utf-8', newline='')
        return True
    return False


def customize(rel, text):
    """고객사용으로 바꾸는 부분"""
    if rel == 'index.html':
        text, n = re.subn(r'\n[ \t]*<div class="office-chips">.*?\n[ \t]*</div>\n', '\n', text, count=1, flags=re.S)
        if n != 1:
            sys.exit('첫 화면에서 영업소 칸을 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
        for old, new in (('<div class="hero-title">영남지사 정보 조회 시스템</div>',
                          f'<div class="hero-title">{CUSTOMER_TITLE}</div>\n'
                          '      <div class="hero-greeting" id="hero-greeting" hidden>'
                          f'<span class="hero-greeting-pad" aria-hidden="true">{TITLE_PAD}</span>'
                          '<span id="hero-greeting-text"></span></div>'),
                         ('<title>영남지사</title>', f'<title>{CUSTOMER_TITLE}</title>')):
            if old not in text:
                sys.exit(f'첫 화면에서 {old} 를 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
            text = text.replace(old, new, 1)
        text = text.replace('</head>', CUSTOMER_CSS + '</head>', 1)
        for title, desc in NAV_DESC.items():
            old = f'<div class="nav-card-title">{title}</div>'
            if old not in text:
                sys.exit(f'첫 화면에서 메뉴 카드 「{title}」 를 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
            text = text.replace(old, f'{old}\n      <div class="nav-card-desc">{desc}</div>', 1)
    if rel in BACK_PAGES:
        old = '>← 영남지사</a>'
        if old not in text:
            sys.exit(f'{rel}: 「← 영남지사」 버튼을 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
        text = text.replace(old, '>🏠 돌아가기</a>', 1)
    if rel.endswith('.html'):                              # 모든 화면에 로그인 잠금(auth/) 연결
        up = '../' * rel.count('/')
        tags = (f'<script src="{up}auth/customers.js?v={auth_version("customers.js")}"></script>'
                f'<script src="{up}auth/auth.js?v={auth_version("auth.js")}"></script>\n')
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
    if stamp_login():
        changed += 1
        print('  갱신 login.html')
    print(f'바뀐 파일 {changed}개')


if __name__ == '__main__':
    main()
