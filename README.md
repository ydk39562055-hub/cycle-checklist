# 경기순환 체크리스트 (웹)

매월 17개 경제지표 차트를 직접 보며 68개 문항을 체크해 국면별(침체·회복·확장·둔화)
점수·확률을 집계하고, 시나리오를 기록·추적하는 도구.
**판단의 자동화가 아니라 "판단 훈련 + 기록"이 목적**입니다.

## 주소
**https://ydk39562055-hub.github.io/cycle-checklist/**
폰·PC 어디서든 이 주소로 들어가면 됩니다. (데이터는 매월 자동 갱신)

## 쓰는 법
1. 위 주소 접속 → **월간 체크** 탭.
2. 지표마다 차트를 보고(ISM은 안내된 사이트에서 확인) 해당되는 문항 체크. **여러 개 체크 가능.**
   - 차트 기간 **1년 / 5년 / 10년** 전환, 마우스 올리면 그 시점 값 표시, 우측에 최근값.
   - 회색 **참고 의견**(그렇다/아니다/애매 + 근거)을 참고. `참고 의견대로 모두 채우기`로 초안 후 수정.
3. **`이 달 저장`** → 클라우드(Supabase)에 자동 동기화.
4. **히스토리/시나리오/자산군** 탭에서 누적·정성분석·자산배분 확인.

## 기기 간 동기화 (로그인 없음)
- 오른쪽 위 **🔗 동기화** → 내 코드가 있습니다. 다른 기기에서 그 코드를 입력하면 같은 기록을 봅니다.
- 코드를 아는 사람만 접근하니 **코드는 공유하지 마세요.** (거래일지와 동일한 방식, `cyc:` 네임스페이스로 분리)

## 자동화 구조
- **데이터**: GitHub Actions가 매월 3일(한국 22시) FRED·yfinance에서 자동 수집 → 사이트 재배포.
  - FRED 키는 저장소 Secret `FRED_API_KEY`(공개 안 됨). 그래프 CSV 호스트는 차단되므로 **FRED 공식 API** 사용.
  - 즉시 갱신하려면: GitHub → Actions → `monthly-data-and-deploy` → Run workflow.
- **저장**: 체크/시나리오/자산수익률은 Supabase(chacha) `journal_sync` 테이블에 동기화 코드별 보관.
- ISM 제조업 PMI만 무료 자동데이터가 없어 수동 — 화면에 MacroMicro·TradingEconomics·Investing·ISM 링크 배너 제공.

## 로컬에서 돌리려면(선택)
`경기순환 체크리스트 시작.bat` 더블클릭 → 데이터 갱신 후 로컬 서버로 열림(`http://localhost:8765`).
점검: `python selftest.py` (문항 68·가중치·이웃가중 6/2/15/9→11.5/12.5/20.5/19.5).

## 파일
```
app_template.html  앱 본체(차트·집계·동기화 전부)
fetch.py 데이터수집 · build.py HTML생성(→ site/index.html) · parse_questions.py 엑셀→문항
.github/workflows/monthly.yml  월간 자동수집+Pages 배포
config/  questions.json(68문항)·indicator_meta.json·asset_returns.json
data/series.json  차트데이터(커밋됨)   data/.fred_key  로컬 키(커밋 금지)
```
