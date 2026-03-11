# Answer AI

보안 우선(local-first)으로 동작하는 로컬 AI 에이전트입니다.

## 핵심 원칙
- 모바일 인터페이스는 다크 테마/빠른 명령 칩이 포함된 깔끔한 PWA UI로 제공됩니다.
- 기본값은 **로컬 전용 모드**입니다.
- 기본값은 **외부 네트워크 차단**입니다.
- API 키는 `~/.answer_ai/config.json`에만 저장되고 파일 권한을 `600`으로 강제합니다.
- 모바일 URL은 토큰 기반으로 보호됩니다.

## 설치 방법 (Answer AI)
1. 저장소를 내려받습니다.
```bash
git clone <REPO_URL>
cd Answer_ai
```

2. 실행 권한을 확인합니다.
```bash
chmod +x answer
```

3. 초기 설정을 실행합니다.
```bash
./answer ai in --local-only
```

4. 에이전트를 실행합니다.
```bash
./answer ai onboard
```

5. (선택) 어디서나 `answer`로 실행하고 싶다면 심볼릭 링크를 추가합니다.
```bash
sudo ln -sf "$(pwd)/answer" /usr/local/bin/answer
answer ai onboard
```


## `answer ai in` 실행해도 아무 일 없는 것처럼 보일 때
- 정상 동작입니다. `answer ai in`은 **설치/초기화만** 수행합니다.
- 실제 실행은 `answer ai onboard`를 입력해야 시작됩니다.
- 초기화 후 바로 실행하려면 아래처럼 사용하세요:
```bash
./answer ai in --onboard-now
```

## 명령어
- `./answer ai in`: 설치/설정
- `./answer ai onboard`: 실행
- `./answer ai proactive`: AI 선제 메시지 1회 생성(크론에서 사용)
- `./answer ai cron-install`: 선제 메시지 cron 등록
- `./answer ai cron-remove`: 선제 메시지 cron 제거

## 빠른 시작 (최고 보안: 로컬 전용)
```bash
./answer ai in --local-only
./answer ai onboard
```

이 모드에서는:
- `browse`는 `localhost/127.0.0.1`만 허용
- `game` 외부 사이트 차단
- `finance`, `video` 외부 API 호출 차단

## 휴대폰 접속이 필요할 때 (LAN 허용)
```bash
./answer ai in --allow-lan-mobile
./answer ai onboard
```

> 주의: LAN 허용 시 같은 네트워크 사용자에게 노출될 수 있으므로 토큰 URL을 절대 공유하지 마세요.

## 외부 API가 정말 필요할 때만
```bash
./answer ai in \
  --allow-external-network \
  --enable-sensitive-data \
  --api openai=YOUR_KEY \
  --video-provider runway \
  --video-api runway=YOUR_VIDEO_KEY
```

- `finance <ticker>`: 외부 시세 조회 (예: `finance aapl.us`)
- `video generate <prompt>`
- `video edit <input_url> <instruction>`

## AI가 먼저 말하게 하는 cron 설정
```bash
# 15분마다 AI 선제 메시지 생성 cron 등록
./answer ai cron-install --every-minutes 15

# 즉시 1회 실행 테스트
./answer ai proactive

# onboard 실행 시 [AI-PROACTIVE]로 자동 표시
./answer ai onboard

# 제거
./answer ai cron-remove
```

또는 초기화 시 자동 설치:
```bash
./answer ai in --install-cron-proactive --cron-every-minutes 15
```

## 보안 권장사항
- 평소에는 `--local-only` 유지
- 외부 API 사용 직후 다시 `--local-only`로 되돌리기
- 모바일 토큰 URL 공유 금지
- 민감 데이터 입력 최소화

---

## English Guide

Answer AI is a local-first, security-focused agent that runs on your PC and can be controlled from mobile (token-protected URL).

### Install
```bash
git clone <REPO_URL>
cd Answer_ai
chmod +x answer
./answer ai in --local-only
./answer ai onboard
```

### Optional: run as global command
```bash
sudo ln -sf "$(pwd)/answer" /usr/local/bin/answer
answer ai onboard
```

### Core commands
- `./answer ai in`: initialize/configure
- `./answer ai in --onboard-now`: initialize and immediately start
- `./answer ai onboard`: run the agent
- `./answer ai proactive`: create one proactive AI message
- `./answer ai cron-install --every-minutes 15`: install proactive cron
- `./answer ai cron-remove`: remove proactive cron

### Security defaults
- Local-only mode enabled by default
- External network blocked by default
- API keys stored in `~/.answer_ai/config.json` with permission `600`
- Mobile control URL protected by token

### Enable mobile LAN access (same network)
```bash
./answer ai in --allow-lan-mobile
./answer ai onboard
```

### Enable external APIs only when needed
```bash
./answer ai in \
  --allow-external-network \
  --enable-sensitive-data \
  --api openai=YOUR_KEY \
  --video-provider runway \
  --video-api runway=YOUR_VIDEO_KEY
```
