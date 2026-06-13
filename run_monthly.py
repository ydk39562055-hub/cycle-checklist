# -*- coding: utf-8 -*-
"""
월 1회 실행: 데이터 갱신 + HTML 재생성.
  python run_monthly.py
이후 python serve.py 로 열어서 체크하세요.
(문항/지표 정의가 바뀌었을 때만 parse_questions.py 를 먼저 실행)
"""
import subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__))

def run(name):
    print(f"\n=== {name} ===")
    r = subprocess.run([sys.executable, os.path.join(HERE, name)])
    if r.returncode != 0:
        print(f"!! {name} 실패(코드 {r.returncode})")
        sys.exit(r.returncode)

if __name__ == "__main__":
    # config/questions.json 이 없으면 파싱부터
    if not os.path.exists(os.path.join(HERE, "config", "questions.json")):
        run("parse_questions.py")
    run("fetch.py")
    run("build.py")
    print("\n완료. 이제  python serve.py  로 여세요 → http://localhost:8765")
