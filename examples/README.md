# didregress 예제

`demo.do`는 Stata 공식 hospdd 인공 자료를 읽어 DID를 추정하고 사전 추세 진단을 수행합니다. Stata 19와 인터넷 연결이 필요합니다.

저장소 루트를 작업 폴더로 설정한 뒤 실행합니다. 출력 폴더는 먼저 생성하세요.

```stata
do examples/demo.do "C:/analysis/did-output"
```

출력 폴더 인수를 생략하면 현재 작업 폴더에 결과를 저장합니다. 실행 전 메모리의 데이터는 preserve/restore로 보존하지만 e() 추정 결과는 DID 결과로 바뀝니다.

## 모형

```stata
didregress (satis) (procedure), group(hospital) time(month)
```

`satis`는 환자 만족도 점수, `procedure`는 새 입원 절차 적용 여부입니다. 반복 횡단면 자료를 사용하며 병원·월 고정효과와 병원 단위 군집 표준오차를 적용합니다. 처치 병원 18개가 4월부터 새 절차를 도입하고 비교 병원 28개는 기존 절차를 유지합니다.

## 검증된 결과

2026-09-29, Windows의 StataNow 19.5 BE와 stata-local MCP에서 실행했습니다.

| 항목 | 결과 |
|---|---:|
| ATET | 0.848***<br>(0.032) |
| 95% 신뢰구간 | [0.783, 0.913] |
| 관측 수 | 7,368 |
| 병원 군집 수 | 46 |
| estat ptrends p값 | 0.4615 |
| estat granger p값 | 0.7239 |

괄호는 군집 표준오차입니다. * p<0.10, ** p<0.05, *** p<0.01. 반올림 전 ATET=0.84798786, 표준오차=0.03211211, p≈4.951e-29입니다. 사전 검정 비기각은 식별 가정을 증명하지 않습니다.

![stcolor DID 진단 그래프](results/didregress_trendplots.png)

왼쪽은 관측 평균, 오른쪽은 선형 추세 모형입니다. 처치는 4월부터 적용됩니다. 이 그림은 기본 stcolor를 사용한 실제 estat trendplots 출력입니다.

## 생성 파일

- didregress_model.ster: 저장한 추정 결과.
- didregress_trendplots.png: 진단 그래프 이미지.
- didregress_trendplots.gph: Stata 그래프 파일.

MCP는 별도로 코드·실행 로그·결과 스냅샷을 실행 폴더에 저장합니다. 저장소의 그림은 검증 당시 출력이며, demo.do 재실행 시 지정한 출력 폴더에 새 결과가 생성됩니다.

MCP 자동 regression_report는 현재 OLS regress용입니다. 위 표는 실제 DID 실행 수치에 근거해 문서에 정리한 것으로, didregress 자동 보고 기능을 추가한 것은 아닙니다.

[Stata 공식 DID 설명](https://www.stata.com/features/overview/difference-in-differences-DID-DDD/) · [공식 예제 데이터](https://www.stata-press.com/data/r19/hospdd.dta)
