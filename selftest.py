# -*- coding: utf-8 -*-
"""자가 검증: 문항/가중치 구조 + 이웃가중 계산 + 더미 저장→집계."""
import json, os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
def load(p): return json.load(open(os.path.join(HERE, p), encoding="utf-8"))

PH = ["침체", "회복", "확장", "둔화"]

def neighbor(raw):
    nb = {}
    for i, p in enumerate(PH):
        prev, nxt = PH[(i+3) % 4], PH[(i+1) % 4]
        nb[p] = raw[p] + 0.5*raw[prev] + 0.5*raw[nxt]
    return nb

def main():
    ok = True
    # 1) 문항 수 / 가중치
    q = load("config/questions.json")["questions"]
    n = len(q)
    print(f"[1] 문항 수 {n} (기대 68) -> {'OK' if n==68 else 'FAIL'}")
    ok &= n == 68
    by_phase = {p: 0 for p in PH}
    for x in q:
        by_phase[x["phase"]] += x["weight"]
    print(f"    국면별 만점(가중치합): {by_phase}")
    # 침체 만점이 강의예시(확장15 등)를 담을 수 있는 구조인지: 각 국면 만점 23
    ok &= all(v == 23 for v in by_phase.values())
    print(f"    각 국면 만점 23 동일 -> {'OK' if all(v==23 for v in by_phase.values()) else 'FAIL'}")
    # 원자재 1점 예외
    comm = [x for x in q if x["indicator_id"] == "spgsci"]
    print(f"    원자재 문항 가중치 {[x['weight'] for x in comm]} (기대 전부 1) -> {'OK' if all(x['weight']==1 for x in comm) else 'FAIL'}")
    ok &= all(x["weight"] == 1 for x in comm)
    # 통화량&금리 2점
    mon = [x for x in q if x["category"] == "통화량&금리"]
    print(f"    통화량&금리 가중치 {sorted(set(x['weight'] for x in mon))} (기대 [2]) -> {'OK' if all(x['weight']==2 for x in mon) else 'FAIL'}")
    ok &= all(x["weight"] == 2 for x in mon)

    # 2) 이웃가중 자가테스트
    raw = {"침체": 6, "회복": 2, "확장": 15, "둔화": 9}
    nb = neighbor(raw)
    exp = {"침체": 11.5, "회복": 12.5, "확장": 20.5, "둔화": 19.5}
    print(f"[2] 이웃가중 6/2/15/9 -> {nb}")
    print(f"    기대            -> {exp}  -> {'OK' if nb==exp else 'FAIL'}")
    ok &= nb == exp

    # 3) 더미 저장 → 집계 흐름(서버 없이 파일 직접 생성, 히스토리가 읽을 형식)
    recdir = os.path.join(HERE, "data", "records")
    os.makedirs(recdir, exist_ok=True)
    # 회복기 시나리오: 회복 문항 위주로 체크
    checks = {}
    for x in q:
        if x["phase"] == "회복":
            checks[x["seq"]] = True
    rawc = {p: 0 for p in PH}
    for x in q:
        if checks.get(x["seq"]):
            rawc[x["phase"]] += x["weight"]
    nbc = neighbor(rawc)
    s = sum(nbc.values()) or 1
    prob = {p: round(nbc[p]/s*100, 1) for p in PH}
    top = max(PH, key=lambda p: nbc[p])
    rec = {"ym": "1999-12", "asof": "TEST", "checks": checks,
           "scores": {"raw": rawc, "neighbor": nbc, "prob": prob}, "top": top,
           "cli_phase": "확장", "cli_match": top == "확장",
           "disagrees": [], "saved_at": "selftest"}
    with open(os.path.join(recdir, "1999-12.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(f"[3] 더미 기록 저장 data/records/1999-12.json")
    print(f"    원점수 {rawc} / 최다국면 {top} / 확률 {prob}")
    print(f"    회복이 최다국면인가 -> {'OK' if top=='회복' else 'FAIL'}")
    ok &= top == "회복"

    print("\n=== 전체 결과:", "통과 ✅" if ok else "실패 ❌", "===")
    print("(더미 기록은 히스토리 탭 확인용. 지우려면 data/records/1999-12.json 삭제)")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
