# v0.1.2 — 회귀표 기본 형식

- 추정치 아래 행에 표준오차를 괄호로 표시합니다.
- 별표: `* p<0.10`, `** p<0.05`, `*** p<0.01`. 반올림 전 p값을 사용합니다.
- `stata_results.regression_report`에 구조화된 값과 Markdown 표를 추가했습니다. 기존 원자료 반환 형식과 Stata 로그는 유지합니다.
- 일반/강건/군집 표준오차를 추정 결과 그대로 보고합니다. 여러 모형 비교에도 같은 형식을 사용하도록 MCP 안내를 수정했습니다.
- OLS `regress` 결과를 지원하며, 서로 맞지 않는 r(table), 생략·기준항, 불완전한 결과를 보수적으로 처리합니다.
- Windows 자동 설치 ZIP도 0.1.2로 갱신했습니다. 기존 설치 사용자는 새 설치기를 실행하고 Codex를 재시작해 새 대화에서 사용하세요.

검증: 전체 테스트 45개 통과. 설치한 wheel의 실제 MCP 연결에서 auto 데이터 네 모형의 강건한 표준오차와 별표 형식을 확인했습니다.

---

# v0.1.1 — Windows 자동 설치 시험 릴리스

- `stata-mcp-0.1.1-windows-setup.zip` 압축 해제 후 `설치.cmd` 실행으로 설치합니다.
- Python 확인, Stata 탐색/폴더 선택, 전용 환경 생성, 패키지 설치를 자동화합니다.
- 실제 MCP 회귀·그래프 검사가 성공하면 Codex 설정을 등록합니다.
- 기존 설정과 주석을 보존하고 원본을 백업합니다. 기존 stata-local 교체는 별도 동의를 받으며 재실행 시 중복 등록하지 않습니다.
- Claude Desktop 설정 예시와 설치 결과 보고서를 생성합니다. Claude 앱 설정은 자동 변경하지 않습니다.
- Python·Stata 설치와 라이선스는 사용자가 준비해야 합니다. 패키지 설치에 인터넷이 필요합니다.

상세 절차와 경로 지정 방법은 `installer/설치안내.md`를 참고하세요.

검증: 전체 테스트 29개 통과. 실제 배포 ZIP의 새 환경 설치 및 `설치.cmd` 재실행, MCP auto 회귀·그래프 반환, 재실행 시 설정 불변을 확인했습니다. 자세한 범위는 `verification.md`를 참고하세요.

---

# v0.1.0 — 비공개 시험 릴리스

Codex에서 로컬 Stata 분석을 실행하는 첫 시험 버전입니다. 같은 표준 MCP 서버에 Claude Desktop을 연결할 수 있도록 설정 예시를 포함합니다.

## 기능

- Stata 상태와 데이터 메타데이터 조회
- 코드·UTF-8 do-file 실행과 세션 상태 유지
- r(), e(), s() 결과 및 이름이 보존된 행렬 반환
- 실행 코드·전체 로그·결과 스냅샷 저장
- 현재 그래프의 PNG 이미지 응답
- 시간 제한과 세션 초기화, 앱별 독립 실행 프로세스

## 검증

Windows, Python 3.12.14, StataNow 19.5 BE에서 17개 테스트가 통과했습니다. 실제 MCP stdio 연결, 회귀분석, 그래프 응답, 오류 처리, 시간 초과 및 종료를 검증했습니다. auto 데이터 회귀 결과는 Stata 직접 배치 실행과 일치했습니다. 자세한 내용은 `verification.md`를 확인하세요.

## 설치

Python 가상환경을 만든 다음 Releases에서 받은 wheel을 설치합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\personal_stata_mcp-0.1.0-py3-none-any.whl
```

소스 ZIP에는 `examples/codex.toml`과 `examples/claude_desktop_config.json`이 들어 있습니다. 실제 Python·Stata·작업 폴더 경로를 설정하고 기존 앱 설정에 해당 서버 항목만 추가하세요.

## 현재 범위

- 각 사용자의 Stata 설치가 필요합니다. Stata 본체·라이선스·데이터는 배포물에 포함하지 않습니다.
- Claude Desktop 앱, 다른 OS 및 에디션은 아직 검증하지 않았습니다.
- 도구는 로컬 사용자 권한으로 Stata 코드를 실행하며 보안 샌드박스가 아닙니다.
- 처음에는 비공개 저장소의 초대받은 사용자만 사용할 수 있습니다.
- 아직 공개 배포하거나 PyPI에 게시하지 않았습니다.
