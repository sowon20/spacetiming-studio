# RESET FLOW – 시공간 스튜디오 부감독

이 문서는 **“무엇을 어디까지 리셋할지”**를 빠르게 결정하고, 항상 같은 절차로 되돌릴 수 있게 하기 위한 정리용이다.  
인격/불탄방/소울은 절대 건드리지 않는다.

---

## [A] UI 리셋 (브라우저 화면만 비우기)

> 부감독 인격/기억은 그대로 두고, **현재 기기에서 보이는 말풍선만** 지우고 싶을 때.

### 1. 각 브라우저에서 실행

개발자 도구 콘솔 또는 주소창 북마클릿 등으로 아래 실행:

```js
localStorage.removeItem("director_chat_messages_v2");
```

### 2. 결과

- 해당 기기에서 채팅 히스토리 말풍선만 지워진다.
- 서버 쪽 `recent_context.json`, `portal_history/`, `memory/`는 그대로 유지된다.

---

## [B] 대화 리셋 (이번 프로젝트 대화/맥락만 싹 포맷)

> 인격/불탄방/장기 아카이브는 유지하고, **이번 실험/프로젝트에서 쌓인 대화와 단기 기억만** 초기화하고 싶을 때.

### 1. Pi (서버)에서 실행

```bash
cd ~/spacetiming-studio

# 1) 단기기억 초기화
echo '[]' > director_server_v1/storage/recent_context.json

# 2) 포털 히스토리 초기화
: > portal_history/sowon.chat.jsonl
: > portal_history/sowon.chat.mac.jsonl
: > portal_history/sowon.chat.pi_boot.backup.jsonl

# 3) 메모리 파일 초기화 (이번 세션에서 쌓인 장기/중간 기억)
rm -f memory/*.jsonl

# 4) 서비스 재시작
sudo systemctl restart spacetiming-director.service
sudo systemctl restart spacetiming-portal.service
```

### 2. 각 브라우저에서 실행 (UI 정리)

```js
localStorage.removeItem("director_chat_messages_v2");
```

### 3. 결과

- 인격/소울/불탄방/akashic/portal_history 아카이브 구조는 그대로.
- **이번 세션에서 쌓인 대화 맥락/단기기억/히스토리만** 리셋된 상태에서 새로 시작.

---

## [C] 로컬 캐시 꼬임 해제 (STORAGE_KEY 버전업)

> 브라우저 캐시가 애매하게 꼬였거나, **완전 새 공책 기분으로 UI를 새로 쓰고 싶을 때.**

### 1. `portal/app.js` 수정

파일 상단에서:

```js
const STORAGE_KEY = "director_chat_messages_v2";
```

를 예를 들어 다음처럼 버전업:

```js
const STORAGE_KEY = "director_chat_messages_v3";
```

### 2. 효과

- 새 키(`director_chat_messages_v3`) 기준으로 **완전히 새로운 채팅 공책**을 쓴다.
- 기존 v2 히스토리는 브라우저 `localStorage` 안에 남아 있지만, 앱에서는 자동으로 읽지 않는다.
- 필요하면 나중에 개발자 도구에서 수동으로 정리 가능:
  ```js
  localStorage.removeItem("director_chat_messages_v2");
  ```

---

## [D] 손대지 말 것 (항상 보존)

리셋 시 **절대 삭제/포맷하지 말아야 할 것들**:

- `identity/` 전체  
  - 특히: `identity/identity.soul`, `identity/sowon.companion.soul`
- `akashic/` 전체
- `portal_history/` 전체 (아카이브 관점에서 보존, 단 B 플로우에서 특정 파일 비우기는 허용)
- `memory/` 폴더 자체 (폴더는 유지, 파일만 리셋)

> 요약: **사람(인격)과 기원 서사, 아카이브 폴더는 항상 남겨둔다.**  
> 리셋은 “이번 판 도화지 정리”까지만 한다.
