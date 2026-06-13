# -*- coding: utf-8 -*-
"""
한 번 클릭 실행기.
  - data/series.json 이 없거나 25일 넘게 오래됐으면 -> 데이터 갱신(fetch+build) 자동
  - 그 다음 서버를 켜고 브라우저를 자동으로 엶
사용자는 이 파일을 부르는 .bat 만 더블클릭하면 됩니다.
"""
import os, sys, json, subprocess, datetime as dt
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
SERIES = os.path.join(HERE, "data", "series.json")
MAX_AGE_DAYS = 25

def data_is_stale():
    if not os.path.exists(SERIES):
        return True
    try:
        asof = json.load(open(SERIES, encoding="utf-8")).get("asof")
        d = dt.date.fromisoformat(asof)
        return (dt.date.today() - d).days >= MAX_AGE_DAYS
    except Exception:
        return True

def run(name):
    r = subprocess.run([sys.executable, os.path.join(HERE, name)])
    if r.returncode != 0:
        print(f"!! {name} 실패(코드 {r.returncode}). 인터넷 연결을 확인하세요.")
        input("엔터를 누르면 그래도 계속합니다...")

if __name__ == "__main__":
    if data_is_stale():
        print("데이터가 오래됐습니다 → 최신 경제데이터를 받아옵니다 (1~2분)…\n")
        if not os.path.exists(os.path.join(HERE, "config", "questions.json")):
            run("parse_questions.py")
        run("fetch.py")
        run("build.py")
        print("\n데이터 갱신 완료.\n")
    else:
        print("데이터가 최신입니다 → 바로 엽니다.\n")
    # 서버 실행(브라우저 자동 오픈 포함)
    run("serve.py")
