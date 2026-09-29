# Stata Local MCP

Codex에서 로컬 Stata를 실행하는 개인용 첫 버전입니다. 표준 MCP stdio를 사용하므로 Claude Desktop에도 같은 서버를 연결할 수 있습니다. Windows StataNow19/BE에서 검증하며, 다른 운영체제·에디션은 검증 전입니다.

## Codex에서 시작하기

**Windows 자동 설치:** [Releases](https://github.com/seokjinwoo/stata-mcp/releases)의 `stata-mcp-0.1.3-windows-setup.zip`을 내려받아 **모두 압축 풀기 → 설치.cmd 더블클릭**으로 실행하세요. 설치된 Python과 Stata를 확인하고, 전용 환경 생성·패키지 설치·실제 회귀/그래프 검사·Codex 설정 등록을 진행합니다. 완료 후 Codex를 완전히 종료했다가 새 대화를 여세요.

64비트 Python 3.11 이상(검증 버전 3.12), 정상 실행되는 Stata와 라이선스, 인터넷이 필요합니다. Python·Stata 본체는 자동 설치하지 않습니다. Python이 없으면 설치 안내를 표시합니다. 기존 설정은 백업하며 `stata-local`이 이미 다르게 설정되어 있으면 교체 여부를 묻습니다. 다른 설정은 보존합니다. [자세한 자동 설치 안내](installer/설치안내.md)를 참고하세요.

서버는 `%LOCALAPPDATA%\StataMCP\envs\0.1.3`에 설치합니다. Claude Desktop용 JSON 예시도 생성하지만 Claude 앱 설정을 자동 변경하지는 않습니다. 자동 설치 ZIP은 GitHub 로그인 후 다운로드하며, Git·Docker·Node.js는 필요하지 않습니다.

아래는 수동 설치를 사용하는 경우의 절차입니다.

아래 설치 절차를 완료하고 `examples/codex.toml`을 자신의 경로에 맞게 설정합니다. Codex에 등록한 후 MCP 서버를 다시 시작하고 새 대화에서 다음처럼 요청하세요.

> stata-local의 stata_status로 연결 상태를 확인한 뒤, Stata 공식 hospdd 예제에서 didregress (satis) (procedure), group(hospital) time(month)를 실행해 줘. ATET와 병원 단위 군집 표준오차, 표본 수를 보고하고, estat ptrends와 estat granger로 사전 추세를 점검한 뒤 stcolor 스킴으로 estat trendplots를 그려 줘. 실행 로그 경로도 보여 줘.

실행 가능한 예제는 `examples/demo.do`입니다. Stata 19와 예제 자료를 내려받을 인터넷 연결이 필요합니다. 출력 폴더를 인수로 지정할 수 있습니다. 자동 회귀표 `regression_report`는 현재 OLS `regress`용이므로, `didregress`에서는 Stata 로그와 원래 추정 결과를 확인합니다.

이어지는 그래프 요청:

> hospdd 자료의 DID 모형을 실행한 세션에서 estat trendplots를 stcolor 스킴으로 그리고 stata_run의 export_graph를 켜서 보여 줘.

현재 대화의 도구 목록은 자동 갱신되지 않을 수 있습니다. 새 대화에서도 없으면 Codex의 MCP 설정에서 `stata-local`을 다시 시작하거나 앱을 다시 시작하세요.

## 설치

Python 3.11 이상(검증 버전 3.12), 적법하게 사용할 수 있는 Stata 설치와 해당 PyStata가 필요합니다. Stata는 배포물에 포함하지 않습니다. 아래 명령은 이 프로젝트 폴더에서 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
```

`examples/codex.toml`의 Python·Stata·작업 폴더 경로를 실제 절대 경로로 바꾸고 Codex 설정에 **해당 서버 항목만** 추가합니다. 기존 설정 파일 전체를 교체하지 마세요.

Claude Desktop에는 `examples/claude_desktop_config.json`의 `mcpServers.stata-local` 항목을 기존 설정에 합칩니다. 앱의 개발자 설정에서 로컬 MCP 설정 파일을 열 수 있습니다. Claude Desktop 실제 연결은 아직 검증하지 않았습니다.

## 제공 도구

| 도구 | 기능 |
|---|---|
| `stata_status` | 필요 시 세션을 시작하고 버전·에디션·세션 ID 확인 |
| `stata_describe` | 현재 데이터의 관측치 수·변수 이름·형식·라벨 조회 |
| `stata_run` | 코드 또는 UTF-8 do-file 실행, 코드·로그 저장, 선택적으로 현재 그래프 PNG 반환 |
| `stata_results` | 마지막 성공 실행 직후의 r(), e(), s()와 행렬 이름·값 조회 |
| `stata_reset` | 메모리의 데이터·추정치·매크로·프로그램을 버리고 새 세션 시작 |

`stata_run`에는 `code`와 `do_file` 중 하나만 전달합니다. `timeout`은 초 단위이며 기본값은 120초입니다. `export_graph=true`이면 실행 후 **현재 그래프 하나**를 내보냅니다. 새 그래프를 만들지 않았다면 이전 그래프가 반환될 수 있으므로 그래프 생성과 내보내기를 같은 요청에서 수행하세요. 원래 그래프 생성 성공과 내보내기 성공은 별개이며 내보내기 실패는 `warning`에 기록됩니다.

## 상태와 결과의 의미

### 회귀표 기본 형식

회귀표는 **계수와 같은 셀 안에서 `<br>`로 줄바꿈한 뒤 괄호로 표준오차**를 표시합니다. 별표는 반올림 전 p값으로 `* p<0.10`, `** p<0.05`, `*** p<0.01`을 적용합니다. 괄호에 p값을 넣지 않습니다. 여러 모형은 열로 나란히 비교하며 표본 수, R², 수정 R²를 함께 보고합니다. 사용자가 다른 형식을 명시하면 그 요청을 따릅니다.

`stata_results`의 `regression_report`에는 이 형식의 Markdown과 구조화된 추정치·표준오차·p값·별표가 포함됩니다. 기존 `r`, `e`, `s`와 원래 Stata 로그는 유지합니다. 표준오차는 추정 시 사용한 일반/강건/군집 방식을 그대로 표시하며 자동으로 추정 방식을 바꾸지 않습니다.

자동 표 생성은 현재 `regress`(OLS)에 지원합니다. `e(b)`, `e(V)`, 자유도, `r(table)`이 완전하고 일치할 때만 생성합니다. 다른 명령이 r(table)을 덮어썼거나 완전 적합으로 추론값이 정의되지 않으면 `available=false`와 이유를 반환합니다. 필요한 저장 모형을 `estimates replay 모형이름`으로 다시 표시한 뒤 결과를 요청할 수 있습니다. 데이터를 재추정하지 않으며, e()가 이전 모형 결과일 수 있으므로 `command`와 `scope`를 확인하세요. 기준범주·생략항에는 별표를 붙이지 않습니다.

- 서버 인스턴스마다 별도의 Stata 세션을 유지합니다. 두 앱의 데이터와 추정치는 서로 공유하지 않습니다. 열린 Stata GUI 세션과도 별개입니다.
- 명령은 순서대로 실행됩니다. 메모리는 다음 요청까지 유지되며 서버 종료·초기화·시간 초과 시 사라집니다.
- 실패한 실행은 자동 재시도하거나 롤백하지 않습니다. 오류 발생 전에 수행한 변경은 남을 수 있습니다.
- 실패·초기화 뒤 `stata_results`는 오래된 추정치를 반환하지 않습니다. 다만 성공 실행 후의 e()는 Stata 특성상 이전 회귀의 결과가 남아 있을 수 있습니다. `run_id`, `e(cmdline)`과 `scope` 설명을 함께 보세요.
- 출력은 16,000자, 각 결과 네임스페이스는 200개 항목, 문자열은 4,000자, 행렬은 4,096개 셀 및 256열로 제한됩니다. 생략 여부가 표시됩니다. Stata 결측치(. 및 .a~.z)는 모두 JSON null로 반환되므로 확장 결측치 구분은 보존되지 않습니다.
- 전체 텍스트 로그는 파일에 남습니다. 행렬 스냅샷 파일에는 동일한 크기 제한이 적용됩니다. 큰 행렬 전체가 필요하면 Stata에서 직접 파일로 내보내세요.

## 파일과 재현

작업 폴더의 `runs/<session_id>/<run_id>/`에 `code.do`, `output.log`, `run.json`, 성공 시 `results.json`, 그래프 요청 시 `graph.png`를 저장합니다. 세션 이벤트는 `events.jsonl`에 남습니다. 서버가 관리하는 산출물 경로를 응답에 포함합니다. 사용자가 명령으로 따로 저장한 모든 파일을 자동 추적하지는 않습니다.

상대 `do_file` 경로는 설정한 작업 폴더 기준입니다. 코드 안의 상대 데이터 경로는 **Stata의 현재 작업 폴더** 기준이므로 `cd` 명령으로 바뀔 수 있습니다. 저장된 코드만으로 외부 데이터·ado 패키지·난수 상태 등 모든 의존성이 재현되지는 않습니다. 실제 연구에서는 데이터 경로, 버전, seed와 설치 패키지도 관리하세요.

코드는 UTF-8 do-file로 실행합니다. 요청 간 데이터·global·프로그램은 유지되지만 do-file의 local 매크로는 다음 요청으로 이어지지 않습니다.

## 실행 환경 설정

| 환경 변수 | 설명 | 기본값 |
|---|---|---|
| `STATA_HOME` | `utilities/pystata`가 들어 있는 Stata 설치 폴더 | 필수 |
| `STATA_EDITION` | `be`, `se`, `mp` | `be` |
| `STATA_WORKDIR` | 입력 상대 경로 및 산출물의 기준 폴더 | `./stata-work` |
| `STATA_TIMEOUT` | 분석 요청 제한 시간(초) | `120` |
| `STATA_STARTUP_TIMEOUT` | Stata 초기화 제한 시간(초) | `60` |

Codex 예시는 도구 호출 제한을 240초로 설정합니다. 분석 제한을 늘릴 때는 앱의 도구 호출 제한도 초기화·종료 시간을 포함할 만큼 늘리세요. 한글과 공백 경로를 지원합니다. Stata 문자열/매크로와 충돌하는 큰따옴표, 줄바꿈, 백틱, 달러 기호가 든 작업 폴더는 사용하지 않습니다.

위 설치 방법처럼 독립 Python 환경을 권장합니다. Codex에 포함된 Python으로도 시험했지만, 해당 런타임이 제거되거나 위치가 바뀌면 가상환경을 다시 만들어야 합니다.

## 실행 권한과 데이터

임의 Stata 코드와 do-file은 로컬 사용자 권한으로 실행됩니다. 별도 작업 프로세스는 충돌·시간 초과·분석 상태를 분리하기 위한 것이며 파일 접근을 제한하는 보안 샌드박스가 아닙니다. Stata에서 실행한 외부 프로그램까지 강제 종료한다고 보장하지 않습니다.

원자료 행은 메타데이터 조회에서 기본 반환하지 않지만, `list` 등으로 출력한 데이터와 반환 결과·그래프는 연결한 AI 앱에 전달됩니다. 원본을 덮어쓰는 명령은 명시적으로 요청한 경우에만 사용하세요. 로컬 도구를 쓰더라도 AI로 전달하는 결과가 전부 로컬에 머무는 것은 아닙니다.

## 개발·검증

```powershell
.\.venv\Scripts\python.exe -m pip install '.[dev]'
$env:STATA_HOME = 'C:/Program Files/StataNow19'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build
```

실제 Stata가 필요한 테스트는 `STATA_HOME`이 없으면 건너뜁니다. 라이선스·설치가 잘못되면 실패합니다. 검증 범위와 결과는 함께 제공하는 `verification.md`를 참고하세요.

공식 참고: [Codex MCP](https://developers.openai.com/codex/mcp), [PyStata 19](https://www.stata.com/python/pystata19/).

## 배포 상태

현재는 비공개 시험용 0.1.3입니다. GitHub Releases의 wheel은 로컬 Python 환경에 설치하는 패키지이며, GitHub가 Stata를 대신 실행하는 서비스는 아닙니다. 각 사용자의 PC에 Stata가 설치되어 있어야 합니다. 공개 전 지원 범위와 소스 라이선스를 결정할 예정이며, 현재 오픈소스 라이선스는 지정하지 않았습니다.
