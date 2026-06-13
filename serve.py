# -*- coding: utf-8 -*-
"""
로컬 저장 서버 — 기록 유실 방지용. 표준 라이브러리만 사용.

  python serve.py      ->  http://localhost:8765 자동 오픈

저장 위치:
  월간 기록   data/records/<YYYY-MM>.json
  시나리오    data/scenarios/<id>.json   (확정 후 수정 불가 = 박제)
  자산수익률  config/asset_returns.json
"""
import json, os, sys, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "output", "checklist.html")
RECORDS = os.path.join(HERE, "data", "records")
SCENARIOS = os.path.join(HERE, "data", "scenarios")
ASSET = os.path.join(HERE, "config", "asset_returns.json")
PORT = 8765

for d in (RECORDS, SCENARIOS):
    os.makedirs(d, exist_ok=True)

def read_json(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # 조용히
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/", "/index.html", "/checklist.html"):
            if not os.path.exists(HTML):
                return self._send(500, "checklist.html 없음 — 먼저 python build.py 를 실행하세요.", "text/plain")
            return self._send(200, open(HTML, "rb").read(), "text/html")
        if p == "/api/ping":
            return self._send(200, {"ok": True})
        if p == "/api/records":
            out = {}
            for fn in sorted(os.listdir(RECORDS)):
                if fn.endswith(".json"):
                    r = read_json(os.path.join(RECORDS, fn))
                    if r: out[fn[:-5]] = r
            return self._send(200, out)
        if p.startswith("/api/record/"):
            ym = p.rsplit("/", 1)[-1]
            r = read_json(os.path.join(RECORDS, ym + ".json"))
            return self._send(200 if r else 404, r or {"error": "없음"})
        if p == "/api/scenarios":
            out = []
            for fn in sorted(os.listdir(SCENARIOS)):
                if fn.endswith(".json"):
                    s = read_json(os.path.join(SCENARIOS, fn))
                    if s: out.append(s)
            return self._send(200, out)
        if p == "/api/asset_returns":
            return self._send(200, read_json(ASSET, {}))
        return self._send(404, {"error": "not found"})

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            body = self._body()
        except Exception as e:
            return self._send(400, {"error": f"본문 파싱 실패: {e}"})

        if p == "/api/record":
            ym = body.get("ym")
            if not ym:
                return self._send(400, {"error": "ym 없음"})
            with open(os.path.join(RECORDS, ym + ".json"), "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, indent=1)
            return self._send(200, {"ok": True, "saved": f"data/records/{ym}.json"})

        if p == "/api/scenarios":
            sid = body.get("id") or body.get("created") or "scn"
            fn = os.path.join(SCENARIOS, f"{sid}.json")
            if os.path.exists(fn):   # 박제: 덮어쓰기 금지
                return self._send(409, {"error": "이미 존재(박제 보호)"})
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, indent=1)
            return self._send(200, {"ok": True, "saved": fn})

        if p == "/api/asset_returns":
            # 기존 메타(_note/source) 보존
            cur = read_json(ASSET, {})
            cur.update({k: v for k, v in body.items()})
            with open(ASSET, "w", encoding="utf-8") as f:
                json.dump(cur, f, ensure_ascii=False, indent=1)
            return self._send(200, {"ok": True})

        return self._send(404, {"error": "not found"})

def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://localhost:{PORT}"
    print(f"경기순환 체크리스트 서버 실행 중 → {url}")
    print("종료: Ctrl+C")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n종료")

if __name__ == "__main__":
    main()
