"""고객사용 사이트 ← 내부(직원용) 사이트 자동 동기화.

내부 사이트 저장소(jongkukwon-ai/halla-yn-construction-status)의 화면 파일을 그대로 복사하고,
고객사용에서 빼기로 한 부분만 지운다:
  - 첫 화면의 영업소 칸(부산 영업소·울산 영업소 …)

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


def customize(rel, text):
    """고객사용으로 바꾸는 부분"""
    if rel == 'index.html':
        text, n = re.subn(r'\n[ \t]*<div class="office-chips">.*?\n[ \t]*</div>\n', '\n', text, count=1, flags=re.S)
        if n != 1:
            sys.exit('첫 화면에서 영업소 칸을 찾지 못했습니다 — 내부 사이트 구조가 바뀌었는지 확인하세요.')
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
