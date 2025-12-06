# SYSTEM_OVERVIEW.md

## 1. 한 줄 요약

라즈베리 Pi에서 돌아가는 **시공간 스튜디오 부감독 시스템**이고, 단 하나의 뇌(Gemini 2.0 Flash Live)가 포털·텔레그램·음성 UI의 모든 대화와 판단을 처리하는 구조다.

---

## 2. 전체 구조 (개념도)

- **부감독 뇌 (LLM 서버)**
  - `director_server_v1/main.py`
  - Gemini 2.0 Flash Live 호출 담당
  - 포털/텔레그램/음성 등 모든 채널의 “생각·판단·기획”을 단일 코어로 처리

- **포털 (웹 채팅 UI)**
  - 루트의 `app.py` (FastAPI + Uvicorn, 포트 8000)
  - `/portal/chat.html`에서 채팅 UI 제공
  - `/api/chat`으로 들어온 요청을 **부감독 뇌 서버(8897)** 로 포워딩

- **입출력 채널들**
  - 현재 기준 핵심 채널은 **포털 웹 UI**
  - 이후 텔레그램 봇 / 음성 UI는 동일한 뇌 서버로 붙는 “다른 입구” 역할을 할 예정

- **기억 & 로그**
  - Firestore / Drive 설계는 이미 머릿속에 있고
  - 현재 레포에서는 **포털 히스토리 파일 + memory/*.jsonl** 이 실질적인 기억 레이어 역할

---

## 3. 주요 서비스 & 포트

- **포털 (Portal)**
  - 서비스명: `spacetiming-portal.service`
  - 포트: `8000`
  - 주요 엔드포인트:
    - `GET  /portal/chat.html`  → 채팅 화면
    - `GET  /api/history`       → 서버 공용 히스토리
    - `POST /api/chat`          → 부감독 뇌로 포워딩
    - `POST /api/upload`        → 첨부 파일 업로드

- **부감독 뇌 서버 (Director Core)**
  - 서비스명: `spacetiming-director.service`
  - 포트: `8897`
  - 헬스체크: `GET http://127.0.0.1:8897/health`
  - 역할: 포털/텔레그램 등에서 온 메시지 + 첨부 이미지들을 모아서 Gemini에 넘기고, 응답 생성

> 리셋이나 재시작이 필요하면 **RESET_FLOW.md** 참고.

---

## 4. 업로드 & 이미지 파이프라인

### 4-1. 기본 개념

- 업로드는 **NAS 경로(`/mnt/sowon_cloud/chat_uploads`)에 직접 저장**하는 것이 현재 기준.
- 라즈베리 로컬 "`uploads/`" 폴더는 필요하면 백업/복구용으로만 사용.

### 4-2. 포털 업로드 루트 (app.py)

- `UPLOAD_ROOT = Path("uploads").resolve()`
- 예시 경로:
  - `~/spacetiming-studio/uploads/local_default/IMG_3001.jpeg`
- `/api/upload` 흐름:
  1. 클라이언트가 이미지 첨부 → `POST /api/upload`
  2. `get_upload_dir(profile)`가 `UPLOAD_ROOT / <profile>` 하위에 디렉터리 만들고 저장
  3. 응답 JSON에 다음 정보 포함
     - `name`, `saved_as`, `url`, `upload_profile`, `server_path`

### 4-3. 부감독 뇌에서의 이미지 처리 (director_server_v1)

- `UPLOAD_ROOT = Path(os.getenv("UPLOAD_ROOT", "uploads")).resolve()`
- `/chat` 엔드포인트에서:
  - `req.attachments`를 돌면서 실제 파일 경로 후보를 순서대로 탐색
    1. `url` 기반 (`/uploads/...` → `UPLOAD_ROOT` 이하로 매핑)
    2. `server_path` 필드가 있으면 그 값을 사용 (또는 `UPLOAD_ROOT/server_path`)
    3. `upload_profile + name` 조합 → `UPLOAD_ROOT/<profile>/<name>`
  - 실제 존재하는 파일을 찾으면 `PIL.Image.open()`으로 열어서 `image_parts`에 추가
  - `image_parts`가 비어 있지 않으면
    - `contents = image_parts + [final_prompt]`
    - `model.generate_content(contents)` 호출
  - 없으면 텍스트만 보내는 일반 채팅 모드로 동작

> 요약: **포털이 첨부 메타를 넘기고, 뇌 서버가 실제 파일을 찾아서 Gemini에 같이 던지는 구조**까지 구현 완료.

---

## 5. 기억 & 히스토리 구조

### 5-1. 소울 / 인격

- 메인 인격 파일: `identity/sowon.companion.soul`
  - `[identity]`, `[roles]`, `[temperament]` 등 부감독의 성격/역할 정의
  - `[io_limits]`에서 이미지/파일 해석 시의 태도·제약 규칙 관리

### 5-2. 불탄방 기억 레이어

- `assistant/memory/burned_room.v1.micro.jsonl`
  - 전체 대화의 “지도 요약” 역할
- `assistant/memory/burned_room.v1.txtmicro.jsonl`
  - 원본 텍스트 리듬을 살린 마이크로 요약

> 이 둘을 통해, 부감독이 과거 대화의 지형과 분위기를 같이 참고할 수 있게 설계됨.

### 5-3. 포털 히스토리

- 파일 위치
  - `portal_history/sowon.chat.jsonl`
  - `portal_history/sowon.chat.mac.jsonl`
- `app.py::_load_history()` 동작
  - 두 파일을 읽어 `(id|role|text)` 기준으로 dedup
  - `HistoryItem(id, role, content, timestamp, attachments)` 구조로 정리
  - `id` 기준 정렬 후, 뒤에서 `limit` 개만 슬라이스해서 `/api/history` 응답에 사용

---

## 6. 리셋 & 복구 기준점

자세한 커맨드와 순서는 **`RESET_FLOW.md`** 에 정리되어 있고, 요지는 다음과 같다.

- **맥락 리셋 (이번 프로젝트 대화만 초기화)**
  - `director_server_v1/storage/recent_context.json` 비우기
  - `portal_history/*.jsonl` 히스토리 비우기
  - `memory/*.jsonl` 삭제
  - 두 서비스 재시작
    - `sudo systemctl restart spacetiming-director.service`
    - `sudo systemctl restart spacetiming-portal.service`
  - 브라우저에서 `localStorage.removeItem("director_chat_messages_v2")`

> 요약: **뇌/인격/불탄방 기억은 유지하면서, “이번 방의 대화”만 깨끗하게 지우는 리셋 플로우**가 준비되어 있다.

---

## 7. 앞으로 확장 포인트 (스냅샷 기준)

- **이미지 파이프라인 최종 안정 체크**
  - 기준 상태: `UPLOAD_ROOT = "/mnt/sowon_cloud/chat_uploads"` (NAS)
  - 체크 포인트:
    - 폰에서 이미지 첨부 → 말풍선 썸네일 정상 표시
    - Pi에서 `ls uploads/local_default`로 파일 생성 확인
    - 부감독이 이미지 내용에 대해 실제 보이는 걸 이야기하는지 확인

- **NAS 전략 확정**
  - 옵션 A: 지금처럼 로컬 `uploads/` 사용 + 필요할 때 NAS로 `rsync` 백업
  - 옵션 B: `UPLOAD_ROOT` 자체를 `/mnt/sowon_cloud/chat_uploads`로 바꾸고, NAS 마운트/권한을 완전히 안정화
  - 현재 이 문서는 **옵션 B 상태를 기준점**으로 삼고 있다.

- **iOS 홈앱 레이아웃 & 말풍선 메뉴 버그**
  - 키보드 등장/사라짐 시 뷰 튀는 문제
  - 짧은 말풍선 길게 눌렀을 때 메뉴가 화면 밖으로 나가는 문제
  - JS에서 viewport 변화 감지 + 메뉴 위치 보정 로직 추가 예정

---

이 문서는 “갈아엎기 전 마지막 스냅샷” 개념이고, 
**지금 이 상태에서 시스템을 어떻게 이해하고 이어서 작업하면 되는지**에만 집중해서 정리한 개요다.
