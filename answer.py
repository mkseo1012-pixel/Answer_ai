#!/usr/bin/env python3
"""Answer AI CLI (local-first, security-focused)."""
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
    "apis": {"openai": "", "anthropic": "", "google": "", "xai": ""},
    "video": {
        "provider": "runway",
        "apis": {"runway": "", "pika": "", "luma": ""},
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
        "allow_external_network": False,
        "local_only_mode": True,
    },
    "mobile_bridge": {
        "enabled": True,
        "bind_host": "127.0.0.1",
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


def secure_write_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(CONFIG_PATH, 0o600)


def ensure_config() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        config = deep_merge(DEFAULT_CONFIG, {})
        config["mobile_bridge"]["auth_token"] = secrets.token_urlsafe(18)
        secure_write_config(config)
    loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    normalized = deep_merge(DEFAULT_CONFIG, loaded)
    if not normalized["mobile_bridge"].get("auth_token"):
        normalized["mobile_bridge"]["auth_token"] = secrets.token_urlsafe(18)
    secure_write_config(normalized)
    return normalized


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
    print("1) 기본값은 로컬 전용(local_only_mode)입니다. 외부 네트워크 통신은 차단됩니다.")
    print("2) 민감 기능(금융/시스템)은 기본 비활성화입니다.")
    print("3) API 키는 ~/.answer_ai/config.json(권한 600)에만 저장합니다.")
    print("4) 모바일 URL의 토큰을 공유하면 원격 제어가 가능하므로 절대 공유하지 마세요.")
    print("5) 외부 API 기능을 켜면 정보 유출 가능성이 커집니다. 꼭 필요할 때만 사용하세요.")
    print(f"\n현재 local_only_mode: {config['safety'].get('local_only_mode')}")
    print(f"현재 allow_external_network: {config['safety'].get('allow_external_network')}")


def normalize_url(raw: str) -> str:
    return raw if raw.startswith(("http://", "https://")) else f"https://{raw}"


def is_local_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def fetch_stock_price(ticker: str) -> str:
    safe_ticker = ticker.lower()
    url = f"https://stooq.com/q/l/?s={urllib.parse.quote(safe_ticker)}&f=sd2t2ohlcv&h&e=csv"
    with urllib.request.urlopen(url, timeout=8) as response:
        rows = response.read().decode("utf-8", errors="ignore").splitlines()
    if len(rows) < 2:
        return "데이터를 가져오지 못했습니다."
    cols = rows[1].split(",")
    if cols[0].upper() == "N/D":
        return "티커를 찾지 못했습니다. 예: aapl.us"
    symbol, date, time_, open_, high, low, close, volume = cols
    return f"[{symbol}] {date} {time_} O:{open_} H:{high} L:{low} C:{close} V:{volume}"


def post_json(url: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
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
<!doctype html><html lang='ko'><head>
<meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>Answer AI Local Mobile</title>
<link rel='manifest' href='/manifest.json?token={token}' />
<style>body{{font-family:sans-serif;margin:16px}}input,button{{font-size:16px;padding:10px}}input{{width:100%}}button{{margin-top:8px;width:100%}}</style>
</head><body>
<h3>Answer AI (Local)</h3>
<p>로컬 장치 제어용입니다. 토큰 URL은 비공개로 유지하세요.</p>
<form action='/send' method='get'>
<input type='hidden' name='token' value='{token}' />
<input name='cmd' placeholder='browse http://localhost:3000' />
<button type='submit'>명령 전송</button></form>
<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js?token={token}');}}</script>
</body></html>
"""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]

        if path in {"/", "/app"}:
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
                "name": "Answer AI Local",
                "short_name": "AnswerAI",
                "start_url": f"/app?token={token}",
                "display": "standalone",
                "background_color": "#ffffff",
                "theme_color": "#111827",
                "icons": [],
            }
            self._write(HTTPStatus.OK, json.dumps(manifest), "application/manifest+json")
            return

        if path == "/sw.js":
            if not self._is_authorized():
                self._write(HTTPStatus.FORBIDDEN, "invalid token", "text/plain")
                return
            self._write(HTTPStatus.OK, "self.addEventListener('fetch', () => {});", "application/javascript")
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

    def is_external_allowed(self) -> bool:
        safety = self.config.get("safety", {})
        return bool(safety.get("allow_external_network", False) and not safety.get("local_only_mode", True))

    def execute(self, cmd: str) -> None:
        tokens = cmd.split()
        if not tokens:
            return
        action = tokens[0].lower()

        if action == "browse" and self.config["safety"].get("allow_browser", True):
            url = normalize_url(tokens[1]) if len(tokens) > 1 else "http://localhost"
            if self.config["safety"].get("local_only_mode", True) and not is_local_url(url):
                print("[SECURITY] local_only_mode 활성화: localhost URL만 허용됩니다.")
                return
            webbrowser.open(url)
            print(f"[BROWSER] 열기: {url}")
            return

        if action == "game" and self.config["safety"].get("allow_game", True):
            if self.config["safety"].get("local_only_mode", True):
                print("[SECURITY] local_only_mode 활성화: 외부 게임 사이트 실행 차단.")
                return
            game = tokens[1].lower() if len(tokens) > 1 else "tetris"
            game_url = {"tetris": "https://tetris.com/play-tetris", "chess": "https://www.chess.com/play/computer"}.get(
                game, "https://itch.io/games/free"
            )
            webbrowser.open(game_url)
            print(f"[GAME] {game} 실행: {game_url}")
            return

        if action == "manage":
            if tokens[1:] and tokens[1].lower() == "status":
                print(f"[SYSTEM] OS={os.name}, CWD={os.getcwd()}")
            else:
                print("[SYSTEM] 지원 명령: manage status")
            return

        if action == "finance":
            if not self.config["safety"].get("allow_sensitive_data", False):
                print("[SENSITIVE] 차단됨: --enable-sensitive-data로 활성화하세요.")
                return
            if not self.is_external_allowed():
                print("[SECURITY] 외부 네트워크 차단 상태입니다. finance 명령 실행 불가.")
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
        if not self.is_external_allowed():
            print("[SECURITY] 외부 네트워크 차단 상태입니다. video 명령 실행 불가.")
            return
        if len(tokens) < 3:
            print("[VIDEO] 사용법: video generate <프롬프트> | video edit <input_url> <지시문>")
            return
        mode = tokens[1].lower()
        provider = self.config.get("video", {}).get("provider", "runway")
        endpoint = self.config.get("video", {}).get("endpoints", {}).get(provider, "")
        token = self.config.get("video", {}).get("apis", {}).get(provider, "")
        if not endpoint or not token:
            print(f"[VIDEO] {provider} 설정 필요: --video-provider/--video-api/--video-endpoint")
            return
        payload: dict[str, Any] = {"provider": provider}
        if mode == "generate":
            payload["prompt"] = " ".join(tokens[2:])
        elif mode == "edit" and len(tokens) >= 4:
            payload["input_url"] = tokens[2]
            payload["instruction"] = " ".join(tokens[3:])
        else:
            print("[VIDEO] edit 모드는 video edit <input_url> <지시문>")
            return
        try:
            result = post_json(endpoint, payload, token)
        except urllib.error.URLError as exc:
            print(f"[VIDEO] API 요청 실패: {exc}")
            return
        print(f"[VIDEO] 요청 완료 ({provider}): {json.dumps(result, ensure_ascii=False)}")


def get_lan_ip() -> str:
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
        print("[INFO] qrcode 모듈이 없어 URL만 출력합니다.")
    print(f"모바일 접속 URL: {url}")


def cmd_in(args: argparse.Namespace) -> None:
    config = ensure_config()
    if args.api:
        config.setdefault("apis", {}).update(parse_key_value_args(args.api, "API"))
    if args.provider:
        config["provider"] = args.provider
    if args.video_api:
        config.setdefault("video", {}).setdefault("apis", {}).update(parse_key_value_args(args.video_api, "영상 API"))
    if args.video_endpoint:
        config.setdefault("video", {}).setdefault("endpoints", {}).update(
            parse_key_value_args(args.video_endpoint, "영상 endpoint")
        )
    if args.video_provider:
        config.setdefault("video", {})["provider"] = args.video_provider
    if args.enable_sensitive_data:
        config.setdefault("safety", {})["allow_sensitive_data"] = True
    if args.enable_system_management:
        config.setdefault("safety", {})["allow_system_management"] = True
    if args.allow_external_network:
        config.setdefault("safety", {})["allow_external_network"] = True
        config.setdefault("safety", {})["local_only_mode"] = False
    if args.local_only:
        config.setdefault("safety", {})["local_only_mode"] = True
        config.setdefault("safety", {})["allow_external_network"] = False
    if args.allow_lan_mobile:
        config.setdefault("mobile_bridge", {})["bind_host"] = "0.0.0.0"
    if args.mobile_port:
        config.setdefault("mobile_bridge", {})["port"] = args.mobile_port

    secure_write_config(config)
    show_precautions(config)
    print(f"\n설치/초기화 완료: {CONFIG_PATH}")


def cmd_onboard(args: argparse.Namespace) -> None:
    config = ensure_config()
    runtime = AgentRuntime(config=config)

    mobile_enabled = config.get("mobile_bridge", {}).get("enabled", True)
    if mobile_enabled:
        host = config.get("mobile_bridge", {}).get("bind_host", "127.0.0.1")
        port = int(config.get("mobile_bridge", {}).get("port", 8765))
        token = config.get("mobile_bridge", {}).get("auth_token", "")
        MobileCommandHandler.auth_token = token
        server = ThreadingHTTPServer((host, port), MobileCommandHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        display_host = get_lan_ip() if host == "0.0.0.0" else "127.0.0.1"
        app_url = f"http://{display_host}:{port}/app?token={token}"

        print("\n[모바일 원격 제어]")
        if host == "127.0.0.1":
            print("로컬 전용 모드: 같은 PC에서만 접속 가능(최고 보안).")
        else:
            print("LAN 모드: 같은 네트워크의 휴대폰에서 접속 가능. 토큰 보호 필수.")
        maybe_print_qr(app_url)

    print("\nAnswer AI 실행 중. 명령어 입력 (exit 종료)")
    print("예시) browse http://localhost:3000")
    print("예시) manage status")
    print("예시) finance aapl.us (외부 네트워크 허용 시)")
    print("예시) video generate 샘플 프롬프트 (외부 네트워크 허용 시)\n")

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
    parser = argparse.ArgumentParser(prog="answer", description="Answer AI local-first agent CLI")
    root = parser.add_subparsers(dest="root")

    ai_parser = root.add_parser("ai", help="AI agent commands")
    ai_sub = ai_parser.add_subparsers(dest="action")

    in_cmd = ai_sub.add_parser("in", help="Initialize Answer AI")
    in_cmd.add_argument("--provider")
    in_cmd.add_argument("--api", action="append", default=[], help="provider=API_KEY")
    in_cmd.add_argument("--video-provider")
    in_cmd.add_argument("--video-api", action="append", default=[], help="provider=VIDEO_API_KEY")
    in_cmd.add_argument("--video-endpoint", action="append", default=[], help="provider=https://...")
    in_cmd.add_argument("--mobile-port", type=int)
    in_cmd.add_argument("--allow-lan-mobile", action="store_true", help="휴대폰 접속을 위해 LAN 바인딩 허용")
    in_cmd.add_argument("--allow-external-network", action="store_true", help="finance/video 외부 API 통신 허용")
    in_cmd.add_argument("--local-only", action="store_true", help="로컬 전용 모드 강제(기본값)")
    in_cmd.add_argument("--enable-system-management", action="store_true")
    in_cmd.add_argument("--enable-sensitive-data", action="store_true")
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
