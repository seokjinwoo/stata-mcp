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
