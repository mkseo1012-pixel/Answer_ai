#!/usr/bin/env python3
"""Answer AI CLI prototype.

Usage:
  answer ai in
  answer ai onboard
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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
    "safety": {
        "allow_browser": True,
        "allow_game": True,
        "allow_system_management": False,
        "confirm_destructive_commands": True,
    },
    "mobile_bridge": {
        "enabled": True,
        "port": 8765,
    },
}


def ensure_config() -> dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_api_args(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"잘못된 API 형식: {item}. provider=key 형태로 입력하세요.")
        provider, key = item.split("=", 1)
        parsed[provider.strip()] = key.strip()
    return parsed


def show_precautions() -> None:
    print("\n[주의사항]")
    print("1) 시스템 관리 기능은 중요한 파일/프로세스에 영향을 줄 수 있습니다.")
    print("2) API 키는 config.json에 저장되므로 파일 권한을 안전하게 유지하세요.")
    print("3) 모바일 QR 접속은 같은 네트워크 환경에서만 사용하세요.")
    print("4) 민감한 명령 실행 전 반드시 확인 프롬프트를 확인하세요.\n")


class MobileCommandHandler(BaseHTTPRequestHandler):
    command_queue: "queue.Queue[str]" = queue.Queue()

    def _write(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._write(
                HTTPStatus.OK,
                """
                <html><head><title>Answer AI Remote</title></head>
                <body style='font-family:sans-serif;'>
                <h1>Answer AI Remote</h1>
                <p>아래 버튼으로 에이전트에게 명령을 보낼 수 있습니다.</p>
                <form action='/send'>
                  <input name='cmd' placeholder='browse https://example.com' style='width:320px'/>
                  <button type='submit'>전송</button>
                </form>
                <p>예시: <code>game tetris</code>, <code>browse https://openai.com</code>, <code>manage status</code></p>
                </body></html>
                """,
            )
            return

        if parsed.path == "/send":
            cmd = parse_qs(parsed.query).get("cmd", [""])[0].strip()
            if cmd:
                self.command_queue.put(cmd)
                self._write(HTTPStatus.OK, f"<p>전송 완료: {cmd}</p><a href='/'>돌아가기</a>")
            else:
                self._write(HTTPStatus.BAD_REQUEST, "명령이 비어 있습니다.")
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
            url = tokens[1] if len(tokens) > 1 else "https://www.google.com"
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
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

        print(f"[WARN] 처리할 수 없는 명령: {cmd}")


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
        updates = parse_api_args(args.api)
        for provider, key in updates.items():
            config["apis"][provider] = key
        print(f"API 키 업데이트 완료: {', '.join(updates.keys())}")

    if args.provider:
        config["provider"] = args.provider
        print(f"기본 AI provider 설정: {args.provider}")

    if args.enable_system_management:
        config["safety"]["allow_system_management"] = True

    save_config(config)
    show_precautions()
    print(f"설치/초기화 완료: {CONFIG_PATH}")


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
        server = ThreadingHTTPServer(("0.0.0.0", port), MobileCommandHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://{get_local_ip()}:{port}"
        print("\n[모바일 원격 제어]")
        maybe_print_qr(url)

    print("\nAnswer AI 실행 중. 명령어 입력 (exit 종료)")
    print("예시) browse https://news.ycombinator.com")
    print("예시) game tetris")
    print("예시) manage status\n")

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
    in_cmd.add_argument(
        "--api",
        action="append",
        default=[],
        help="provider=API_KEY 형식. 여러 번 입력 가능",
    )
    in_cmd.add_argument(
        "--enable-system-management",
        action="store_true",
        help="시스템 관리 기능 활성화",
    )
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
