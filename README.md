# Answer AI

`Answer AI`는 데스크톱에서 실행되며, QR 코드로 휴대폰에서 원격 명령을 보낼 수 있는 AI 에이전트 프로토타입입니다.

## 핵심 기능
- `answer ai in`: 다운로드/초기 설정(Provider, API 키, 안전 설정)
- `answer ai onboard`: 에이전트 실행 + 모바일 QR 원격 제어
- 명령 지원
  - `game <name>`: 게임 URL 실행
  - `browse <url>`: 브라우저 열기
  - `manage status`: 시스템 상태 확인
- 다중 API Provider 설정 지원(OpenAI/Anthropic/Google/xAI 등)

## 사용법
```bash
./answer ai in --provider openai --api openai=YOUR_KEY
./answer ai onboard
```

> `qrcode` 패키지가 설치되어 있으면 터미널에 ASCII QR을 보여주고, 없으면 URL을 출력합니다.

## 주의사항
- 같은 네트워크 사용자만 QR URL에 접근하도록 관리하세요.
- 중요한 시스템 변경 명령은 기본적으로 비활성화되어 있습니다.
- API 키는 `~/.answer_ai/config.json`에 저장됩니다.

## 설정 파일
초기 실행 시 아래 파일이 생성됩니다.

- `~/.answer_ai/config.json`

예시:
```json
{
  "provider": "openai",
  "apis": {
    "openai": "",
    "anthropic": "",
    "google": "",
    "xai": ""
  },
  "safety": {
    "allow_browser": true,
    "allow_game": true,
    "allow_system_management": false,
    "confirm_destructive_commands": true
  },
  "mobile_bridge": {
    "enabled": true,
    "port": 8765
  }
}
```
