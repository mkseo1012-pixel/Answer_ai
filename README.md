# Answer AI

`Answer AI`는 PC에서 실행하고, QR 코드로 휴대폰에서 접속해 앱(PWA)처럼 사용할 수 있는 AI 에이전트입니다.

## 주요 기능
- `answer ai in`: 설치/초기화 + provider/API/보안 설정
- `answer ai onboard`: 에이전트 실행 + 모바일 원격 제어 서버 시작
- `finance <ticker>`: 주식 시세 조회(민감정보 기능 활성화 필요)
- `video generate <prompt>` / `video edit <input_url> <instruction>`: 영상 생성/편집 API 요청
- `browse <url>`, `game <name>`, `manage status`

## 빠른 시작
```bash
./answer ai in \
  --provider openai \
  --api openai=YOUR_OPENAI_KEY \
  --enable-sensitive-data \
  --video-provider runway \
  --video-api runway=YOUR_VIDEO_API_KEY

./answer ai onboard
```

## 모바일 앱(PWA) 접속
- `onboard` 실행 시 토큰이 포함된 모바일 URL/QR이 출력됩니다.
- 모바일 브라우저에서 URL을 열고 **홈 화면에 추가**를 누르면 앱처럼 실행할 수 있습니다.
- URL에 토큰이 없거나 틀리면 접근이 차단됩니다.

## 영상 API 설정
기본 endpoint는 예시값이며 Provider 문서에 맞춰 변경하세요.

```bash
./answer ai in \
  --video-provider runway \
  --video-api runway=YOUR_KEY \
  --video-endpoint runway=https://api.runwayml.com/v1/video/jobs
```

## 주의사항
- 주식/금융 정보는 참고용이며 실제 투자 판단은 반드시 직접 검증하세요.
- 영상 생성/편집 API는 과금될 수 있습니다.
- API 키는 `~/.answer_ai/config.json`에 저장됩니다. 파일 권한을 보호하세요.
- 모바일 URL(토큰 포함)을 공유하면 원격 제어가 가능하므로 반드시 비공개로 관리하세요.

## 설정 파일
- `~/.answer_ai/config.json`
- 주요 항목: `apis`, `video.apis`, `video.endpoints`, `safety.allow_sensitive_data`, `mobile_bridge.auth_token`
