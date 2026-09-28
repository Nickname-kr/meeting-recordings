# 회의록 작성 프로그램

Streamlit + Google Sheets로 만든 한국어 회의록 앱입니다. 네이비·청록·화이트의 카드형 UI와 5단계 작성 흐름을 제공합니다.

## 빠른 실행

Python 3.11 이상을 권장합니다. 이 폴더에서 실행하세요.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Secrets가 없으면 체험 모드로 실행됩니다. 체험 기록은 현재 브라우저 세션에만 남습니다. 연결 설정을 했으나 연결이 실패한 경우 오류를 표시하며 체험 모드로 전환하지 않습니다.

## 사용 흐름

1. 회의 제목과 날짜를 입력하고 시작·종료 시간을 선택합니다. 날짜 입력란을 누르면 달력이 열립니다.
2. 참석자를 검색하고 여러 명 선택합니다. 없는 사람은 이름을 입력하고 Enter를 누릅니다.
3. 장소를 선택합니다. 새 장소도 입력하고 Enter로 추가할 수 있습니다.
4. 작성자, 안건, 논의 내용, 결정 사항, 후속 업무를 입력합니다.
5. 미리보기를 확인하고 저장합니다.

새 참석자·장소는 **회의록 저장 후** 다음 회의의 드롭다운에 표시됩니다. 저장 이력에서 목록을 구성하므로 해당 인물이 포함된 모든 행을 직접 삭제하면 목록에서도 사라집니다. 기본 명단은 Secrets의 `[defaults]`에서 지정할 수 있습니다. 작성 단계 이동 시 입력값은 유지되지만 새로고침·탭 종료 시 미저장 초안은 사라질 수 있습니다.

저장된 회의록 메뉴에서 제목·참석자·장소를 검색할 수 있습니다. 다른 사용자의 새 기록은 새로고침 버튼으로 불러옵니다. 이 버전은 저장 후 수정·삭제 UI를 제공하지 않습니다.

## Google Sheets 연결 (최초 한 번)

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 만들거나 선택합니다.
2. API 및 서비스 → 라이브러리에서 **Google Sheets API**를 활성화합니다.
3. IAM 및 관리자 → 서비스 계정에서 계정을 만들고, 키 → 키 추가 → 새 키 만들기 → JSON으로 키를 발급합니다. 조직에서 키 발급을 제한했다면 관리자 설정이 필요합니다.
4. Google 스프레드시트를 하나 만들고 JSON의 `client_email` 주소에 **편집자**로 공유합니다. 링크 전체 공개는 필요 없습니다.
5. URL `https://docs.google.com/spreadsheets/d/여기가_ID/edit`의 ID를 복사합니다.
6. `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사합니다. 스프레드시트 ID와 JSON 키의 각 값을 채웁니다. `private_key`의 `\n`은 예시처럼 이중 따옴표 안에서 보존하세요.
7. 앱을 다시 실행합니다. `Google Sheets 연결됨` 표시를 확인합니다. 최초 연결 시 지정한 회의록 탭과 열 이름이 만들어집니다.

기존 데이터와 섞이지 않도록 **전용 빈 탭**을 지정하세요. 이미 탭이 있으면 첫 행의 열 이름이 정확히 맞아야 합니다. 앱은 다른 탭을 지우거나 덮어쓰지 않습니다. 설정 변경 후 서버를 재시작하세요.

### 저장 구조

한 회의당 한 행, 총 13개 열입니다.

`회의ID / 저장시각 / 회의제목 / 회의일자 / 시작시간 / 종료시간 / 참석자 / 장소 / 안건 / 논의내용 / 결정사항 / 후속업무 / 작성자`

참석자는 JSON 배열 문자열입니다. 날짜는 `YYYY-MM-DD`, 시간은 `HH:MM`, 저장시각은 한국 시간대 ISO 8601 형식입니다. 사용자 입력은 RAW로 저장해 수식으로 실행되지 않습니다. 원본 열 순서와 이름을 변경하지 마세요. 셀당 입력 길이는 45,000자로 제한합니다. 회의는 같은 날 종료하는 일정만 지원합니다.

## GitHub → Streamlit Community Cloud 배포

1. 새 GitHub 저장소에 이 폴더의 **내용**을 올립니다. `.streamlit/config.toml`도 포함하세요. 실제 `secrets.toml`과 서비스 계정 JSON은 올리지 마세요.
2. [Streamlit Community Cloud](https://share.streamlit.io/)에서 앱을 만들고 저장소·브랜치·진입 파일 `app.py`를 선택합니다.
3. 앱의 Secrets 설정에 로컬 `secrets.toml` 내용을 붙여 넣습니다. Python 3.11 이상을 사용하세요.
4. 팀 전용 회의록이면 배포 플랫폼의 접근 제한을 적용하거나 `app_password`를 설정합니다. 공용 비밀번호는 개인별 권한 관리가 아니며, 접속한 사람 모두 같은 회의록을 읽고 추가할 수 있습니다.
5. 배포 후 테스트 회의록 한 건을 저장하고 시트의 행 추가 및 다음 회의에서 참석자 재사용을 확인합니다.

이 전달물에는 실제 계정 키나 시트 연결이 포함되지 않습니다. 실제 Google 저장은 위 설정 후 확인해야 합니다.

## 재시도와 운영 범위

회의별 UUID를 유지하고 저장 전 동일 ID를 확인합니다. 같은 프로세스의 중복 클릭은 잠금으로 보호하고, 저장 응답 유실 후 재시도도 기존 ID를 확인합니다. 여러 서버 프로세스에서 같은 ID를 동시에 저장하는 경우 Sheets는 고유 키 제약/트랜잭션을 제공하지 않아 엄격한 exactly-once 보장은 없습니다. 소규모 팀용이며 대량 기록은 매번 전체 이력을 읽는 현재 구현 대신 데이터베이스·페이지네이션을 권장합니다.

## 검증

```bash
pip install pytest
python -m pytest -q
```

가짜 Sheets 객체로 RAW 저장, 오류 후 재시도, 중복 저장을 검증하고 Streamlit AppTest로 작성 흐름을 확인합니다. 실제 Google API 통합 검증은 별도의 자격 증명이 필요합니다.

## 공식 참고 문서

- https://docs.streamlit.io/1.51.0/develop/api-reference/widgets/st.multiselect
- https://docs.streamlit.io/develop/concepts/connections/secrets-management
- https://docs.gspread.org/en/latest/oauth2.html
- https://docs.gspread.org/en/latest/api/models/worksheet.html
