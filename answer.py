#!/usr/bin/env python3
"""Answer AI CLI.

Usage:
  answer ai in
  answer ai onboard
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import secrets
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".answer_ai"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "openai",
    "apis": {
        "openai": "",
        "anthropic": "",
        "google": "",
        "xai": "",
    },
    "video": {
        "provider": "runway",
        "apis": {
            "runway": "",
            "pika": "",
            "luma": "",
        },
        "endpoints": {
            "runway": "https://api.runwayml.com/v1/video/jobs",
            "pika": "https://api.pika.art/v1/video/jobs",
            "luma": "https://api.lumalabs.ai/v1/video/jobs",
        },
    },
    "safety": {
        "allow_browser": True,
        "allow_game": True,
        "allow_system_management": False,
        "allow_sensitive_data": False,
        "confirm_destructive_commands": True,
    },
    "mobile_bridge": {
        "enabled": True,
        "port": 8765,
        "auth_token": "",
    },
}


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def ensure_config() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        config = deep_merge(DEFAULT_CONFIG, {})
        config["mobile_bridge"]["auth_token"] = secrets.token_urlsafe(18)
        CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    normalized = deep_merge(DEFAULT_CONFIG, loaded)
    if not normalized["mobile_bridge"].get("auth_token"):
        normalized["mobile_bridge"]["auth_token"] = secrets.token_urlsafe(18)
    save_config(normalized)
    return normalized


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_key_value_args(values: list[str], desc: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"잘못된 {desc} 형식: {item}. provider=value 형태로 입력하세요.")
        provider, value = item.split("=", 1)
        parsed[provider.strip()] = value.strip()
    return parsed


def show_precautions(config: dict[str, Any]) -> None:
    print("\n[주의사항]")
    print("1) 시스템/민감정보 기능은 사용자의 책임 하에 활성화하세요.")
    print("2) API 키는 config.json에 저장되므로 파일 권한(600 권장)을 안전하게 유지하세요.")
    print("3) 모바일 접속은 토큰이 포함된 URL만 허용됩니다. URL 공유에 주의하세요.")
    print("4) 주식/금융 정보는 참고용이며, 실제 투자 판단은 반드시 별도 검증이 필요합니다.")
    print("5) 영상 생성/편집 API는 비용이 발생할 수 있으니 Provider 과금 정책을 확인하세요.")
    print(f"\n현재 민감정보 접근: {'활성화' if config['safety'].get('allow_sensitive_data') else '비활성화'}")


def normalize_url(raw: str) -> str:
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw}"


def fetch_stock_price(ticker: str) -> str:
    safe_ticker = ticker.lower()
    url = f"https://stooq.com/q/l/?s={urllib.parse.quote(safe_ticker)}&f=sd2t2ohlcv&h&e=csv"
    with urllib.request.urlopen(url, timeout=8) as response:
        rows = response.read().decode("utf-8", errors="ignore").splitlines()

    if len(rows) < 2:
        return "데이터를 가져오지 못했습니다."

    columns = rows[1].split(",")
    if columns[0].upper() == "N/D":
        return "티커를 찾지 못했습니다. 예: aapl.us, tsla.us"
    symbol, date, time_, open_, high, low, close, volume = columns
    return (
        f"[{symbol}] {date} {time_} O:{open_} H:{high} L:{low} C:{close} V:{volume}"
    )


def post_json(url: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="ignore")
        if not body.strip():
            return {"status": "accepted", "detail": "empty response"}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"status": "accepted", "raw": body[:300]}


class MobileCommandHandler(BaseHTTPRequestHandler):
    command_queue: "queue.Queue[str]" = queue.Queue()
    auth_token: str = ""

    def _write(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _is_authorized(self) -> bool:
        parsed = urllib.parse.urlparse(self.path)
        token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
        return token == self.auth_token

    def _app_html(self, token: str) -> str:
        return f"""
<!doctype html>
<html lang='ko'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <meta name='theme-color' content='#111827' />
  <link rel='manifest' href='/manifest.json?token={token}' />
  <title>Answer AI Mobile</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; margin: 20px; background: #f9fafb; }}
    input, button {{ font-size: 16px; padding: 10px; }}
    input {{ width: 100%; margin-bottom: 10px; }}
    button {{ width: 100%; border: 0; border-radius: 8px; background: #2563eb; color: white; }}
    .example {{ color: #4b5563; font-size: 14px; }}
  </style>
</head>
<body>
  <h2>Answer AI Mobile App</h2>
  <p>PWA로 홈 화면에 추가해서 앱처럼 사용 가능합니다.</p>
  <form action='/send' method='get'>
    <input type='hidden' name='token' value='{token}' />
    <input name='cmd' placeholder='finance aapl.us' />
    <button type='submit'>명령 전송</button>
  </form>
  <p class='example'>예시: game chess / browse openai.com / finance tsla.us / video generate 도시 야경 타임랩스</p>
  <script>
    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('/sw.js?token={token}');
    }}
  </script>
</body>
</html>
"""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]

        if path == "/" or path == "/app":
            if not self._is_authorized():
                self._write(HTTPStatus.FORBIDDEN, "invalid token", "text/plain")
                return
            self._write(HTTPStatus.OK, self._app_html(token))
            return

        if path == "/manifest.json":
            if not self._is_authorized():
                self._write(HTTPStatus.FORBIDDEN, "invalid token", "text/plain")
                return
            manifest = {
                "name": "Answer AI Mobile",
                "short_name": "AnswerAI",
                "start_url": f"/app?token={token}",
                "display": "standalone",
                "background_color": "#f9fafb",
                "theme_color": "#111827",
                "icons": [],
            }
            self._write(HTTPStatus.OK, json.dumps(manifest), "application/manifest+json")
            return

        if path == "/sw.js":
            if not self._is_authorized():
                self._write(HTTPStatus.FORBIDDEN, "invalid token", "text/plain")
                return
            sw = "self.addEventListener('fetch', () => {});"
            self._write(HTTPStatus.OK, sw, "application/javascript")
            return

        if path == "/send":
            if not self._is_authorized():
                self._write(HTTPStatus.FORBIDDEN, "invalid token", "text/plain")
                return
            cmd = urllib.parse.parse_qs(parsed.query).get("cmd", [""])[0].strip()
            if not cmd:
                self._write(HTTPStatus.BAD_REQUEST, "명령이 비어 있습니다.")
                return
            self.command_queue.put(cmd)
            self._write(HTTPStatus.OK, f"<p>전송 완료: {cmd}</p><a href='/app?token={token}'>돌아가기</a>")
            return

        self._write(HTTPStatus.NOT_FOUND, "not found", "text/plain")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


@dataclass
class AgentRuntime:
    config: dict[str, Any]

    def execute(self, cmd: str) -> None:
        tokens = cmd.split()
        if not tokens:
            return

        action = tokens[0].lower()

        if action == "browse" and self.config["safety"].get("allow_browser", True):
            url = normalize_url(tokens[1]) if len(tokens) > 1 else "https://www.google.com"
            webbrowser.open(url)
            print(f"[BROWSER] 열기: {url}")
            return

        if action == "game" and self.config["safety"].get("allow_game", True):
            game = tokens[1].lower() if len(tokens) > 1 else "tetris"
            game_url = {
                "tetris": "https://tetris.com/play-tetris",
                "chess": "https://www.chess.com/play/computer",
                "sudoku": "https://sudoku.com/",
            }.get(game, "https://itch.io/games/free")
            webbrowser.open(game_url)
            print(f"[GAME] {game} 실행: {game_url}")
            return

        if action == "manage":
            sub = tokens[1].lower() if len(tokens) > 1 else "status"
            if sub == "status":
                print(f"[SYSTEM] 운영체제: {os.name}, 작업경로: {os.getcwd()}")
                return
            print("[SYSTEM] 지원하지 않는 관리 명령입니다. (status만 지원)")
            return

        if action == "finance":
            if not self.config["safety"].get("allow_sensitive_data", False):
                print("[SENSITIVE] 차단됨: `answer ai in --enable-sensitive-data`로 활성화하세요.")
                return
            ticker = tokens[1] if len(tokens) > 1 else "aapl.us"
            try:
                print(f"[FINANCE] {fetch_stock_price(ticker)}")
            except urllib.error.URLError as exc:
                print(f"[FINANCE] 조회 실패: {exc}")
            return

        if action == "video":
            self._handle_video(tokens)
            return

        print(f"[WARN] 처리할 수 없는 명령: {cmd}")

    def _handle_video(self, tokens: list[str]) -> None:
        if len(tokens) < 3:
            print("[VIDEO] 사용법: video generate <프롬프트> | video edit <input_url> <지시문>")
            return

        mode = tokens[1].lower()
        provider = self.config.get("video", {}).get("provider", "runway")
        endpoint = self.config.get("video", {}).get("endpoints", {}).get(provider, "")
        token = self.config.get("video", {}).get("apis", {}).get(provider, "")

        if not endpoint or not token:
            print(
                f"[VIDEO] {provider} API 설정이 필요합니다. "
                f"`answer ai in --video-provider {provider} --video-api {provider}=KEY --video-endpoint {provider}=URL`"
            )
            return

        payload: dict[str, Any] = {"provider": provider}
        if mode == "generate":
            payload["prompt"] = " ".join(tokens[2:])
        elif mode == "edit" and len(tokens) >= 4:
            payload["input_url"] = tokens[2]
            payload["instruction"] = " ".join(tokens[3:])
        else:
            print("[VIDEO] edit 모드는 video edit <input_url> <지시문> 형식만 지원합니다.")
            return

        try:
            result = post_json(endpoint, payload, token)
        except urllib.error.URLError as exc:
            print(f"[VIDEO] API 요청 실패: {exc}")
            return

        print(f"[VIDEO] 요청 완료 ({provider}): {json.dumps(result, ensure_ascii=False)}")


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def maybe_print_qr(url: str) -> None:
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        print("[INFO] QR 모듈(qrcode) 미설치 또는 오류. 아래 URL을 직접 열어주세요.")
    print(f"모바일 접속 URL: {url}")


def cmd_in(args: argparse.Namespace) -> None:
    config = ensure_config()

    if args.api:
        updates = parse_key_value_args(args.api, "API")
        config.setdefault("apis", {}).update(updates)
        print(f"기본 AI API 키 업데이트: {', '.join(updates.keys())}")

    if args.provider:
        config["provider"] = args.provider
        print(f"기본 AI provider: {args.provider}")

    if args.video_api:
        v_updates = parse_key_value_args(args.video_api, "영상 API")
        config.setdefault("video", {}).setdefault("apis", {}).update(v_updates)
        print(f"영상 API 키 업데이트: {', '.join(v_updates.keys())}")

    if args.video_endpoint:
        e_updates = parse_key_value_args(args.video_endpoint, "영상 endpoint")
        config.setdefault("video", {}).setdefault("endpoints", {}).update(e_updates)
        print(f"영상 endpoint 업데이트: {', '.join(e_updates.keys())}")

    if args.video_provider:
        config.setdefault("video", {})["provider"] = args.video_provider
        print(f"영상 provider: {args.video_provider}")

    if args.enable_system_management:
        config.setdefault("safety", {})["allow_system_management"] = True

    if args.enable_sensitive_data:
        config.setdefault("safety", {})["allow_sensitive_data"] = True

    if args.mobile_port:
        config.setdefault("mobile_bridge", {})["port"] = args.mobile_port

    save_config(config)
    show_precautions(config)
    print(f"\n설치/초기화 완료: {CONFIG_PATH}")


def cmd_onboard(args: argparse.Namespace) -> None:
    config = ensure_config()
    provider = config.get("provider", "openai")
    key = config.get("apis", {}).get(provider, "")
    if not key:
        print(f"[WARN] {provider} API 키가 비어 있습니다. `answer ai in --api {provider}=YOUR_KEY`로 등록하세요.")

    runtime = AgentRuntime(config=config)
    mobile_enabled = config.get("mobile_bridge", {}).get("enabled", True)

    if mobile_enabled:
        port = int(config.get("mobile_bridge", {}).get("port", 8765))
        token = config.get("mobile_bridge", {}).get("auth_token", "")
        MobileCommandHandler.auth_token = token
        server = ThreadingHTTPServer(("0.0.0.0", port), MobileCommandHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        app_url = f"http://{get_local_ip()}:{port}/app?token={token}"

        print("\n[모바일 원격 제어]")
        print("앱(PWA) 설치: 모바일 브라우저에서 열고 '홈 화면에 추가'를 선택하세요.")
        maybe_print_qr(app_url)

    print("\nAnswer AI 실행 중. 명령어 입력 (exit 종료)")
    print("예시) browse https://news.ycombinator.com")
    print("예시) game tetris")
    print("예시) finance aapl.us")
    print("예시) video generate 드론 샷의 서울 야경 타임랩스\n")

    while True:
        try:
            if mobile_enabled:
                try:
                    mobile_cmd = MobileCommandHandler.command_queue.get_nowait()
                    print(f"[MOBILE] {mobile_cmd}")
                    runtime.execute(mobile_cmd)
                except queue.Empty:
                    pass

            local_cmd = input("> ").strip()
            if local_cmd.lower() in {"exit", "quit"}:
                print("Answer AI 종료")
                break
            runtime.execute(local_cmd)
        except KeyboardInterrupt:
            print("\nAnswer AI 종료")
            break


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="answer", description="Answer AI agent CLI")
    root = parser.add_subparsers(dest="root")

    ai_parser = root.add_parser("ai", help="AI agent commands")
    ai_sub = ai_parser.add_subparsers(dest="action")

    in_cmd = ai_sub.add_parser("in", help="Download/initialize Answer AI")
    in_cmd.add_argument("--provider", help="기본 AI provider (예: openai, anthropic)")
    in_cmd.add_argument("--api", action="append", default=[], help="provider=API_KEY 형식. 여러 번 입력 가능")
    in_cmd.add_argument("--video-provider", help="영상 생성/편집 기본 provider")
    in_cmd.add_argument("--video-api", action="append", default=[], help="provider=VIDEO_API_KEY")
    in_cmd.add_argument("--video-endpoint", action="append", default=[], help="provider=https://...")
    in_cmd.add_argument("--mobile-port", type=int, help="모바일 브리지 포트")
    in_cmd.add_argument("--enable-system-management", action="store_true", help="시스템 관리 기능 활성화")
    in_cmd.add_argument("--enable-sensitive-data", action="store_true", help="주식/민감정보 조회 기능 활성화")
    in_cmd.set_defaults(func=cmd_in)

    onboard_cmd = ai_sub.add_parser("onboard", help="Run Answer AI")
    onboard_cmd.set_defaults(func=cmd_onboard)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
