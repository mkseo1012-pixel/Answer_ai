#!/usr/bin/env python3
"""Lemon AI: 대화와 글쓰기를 지원하는 콘솔 AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re


EXIT_COMMANDS = {"종료", "exit", "quit", "bye", "그만"}


@dataclass
class LemonAI:
    """대화 맥락을 저장하고 응답/글쓰기를 수행하는 간단한 챗봇."""

    name: str = "Lemon AI"
    memory: list[str] = field(default_factory=list)

    def respond(self, message: str) -> str:
        cleaned = message.strip()
        if not cleaned:
            return "아무 말도 입력되지 않았어요. 하고 싶은 이야기를 들려주세요!"

        self.memory.append(cleaned)
        lowered = cleaned.lower()

        if lowered in EXIT_COMMANDS:
            return "대화를 마칠게요. 다음에 또 만나요!"

        # 글쓰기 명령: "글써줘: 주제" 또는 "글 써줘 주제"
        writing_topic = self._extract_writing_topic(cleaned)
        if writing_topic:
            return self._generate_short_writing(writing_topic)

        # 문장 다듬기 명령: "다듬어: 문장"
        refine_text = self._extract_payload(cleaned, prefixes=("다듬어:", "교정:", "고쳐줘:"))
        if refine_text:
            return self._refine_text(refine_text)

        # 요약 명령: "요약: 문장"
        summary_text = self._extract_payload(cleaned, prefixes=("요약:", "정리:", "한줄요약:"))
        if summary_text:
            return self._summarize_text(summary_text)

        if "도움말" in cleaned or "help" == lowered:
            return (
                "할 수 있는 것들:\n"
                "1) 대화하기 (질문, 고민 상담)\n"
                "2) 글쓰기: '글써줘: 주제'\n"
                "3) 문장 다듬기: '다듬어: 문장'\n"
                "4) 요약하기: '요약: 긴 문장'"
            )

        if "이름" in cleaned or "누구" in cleaned:
            return f"저는 {self.name}예요. 대화도 하고, 글도 써드릴 수 있어요."

        if "시간" in cleaned or "몇 시" in cleaned:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            return f"지금 시간은 {now}입니다."

        if re.search(r"(힘들|우울|슬프|지쳤|불안)", cleaned):
            return "많이 버거우셨겠어요. 지금 가장 힘든 한 가지를 말해주면 함께 정리해볼게요."

        if re.search(r"(좋아|행복|신나|기뻐|잘됐)", cleaned):
            return "좋은 소식이네요! 그 기분을 오래 가져가도록 오늘의 한 줄 기록을 남겨볼까요?"

        if len(self.memory) > 1 and ("기억" in cleaned or "방금" in cleaned):
            previous = self.memory[-2]
            return f"방금 전에 '{previous}'라고 말해주셨어요. 그 이야기부터 이어가볼까요?"

        if self._looks_like_question(cleaned):
            return (
                "좋은 질문이에요. 원하는 결과(예: 빠른 해결/깊은 이해/실행 계획) 중 어떤 쪽이 필요한지 말해주면 "
                "더 정확히 도와드릴게요."
            )

        return "좋아요. 더 구체적으로 알려주시면 제가 문장 정리나 글 초안까지 바로 도와드릴게요."

    def _extract_writing_topic(self, text: str) -> str | None:
        explicit = self._extract_payload(text, prefixes=("글써줘:", "글 써줘:", "작성해줘:", "써줘:"))
        if explicit:
            return explicit

        match = re.search(r"글\s*써\s*줘\s*(.*)", text)
        if match:
            topic = match.group(1).strip(" :")
            return topic or "오늘의 다짐"
        return None

    @staticmethod
    def _extract_payload(text: str, prefixes: tuple[str, ...]) -> str | None:
        stripped = text.strip()
        lowered = stripped.lower()
        for prefix in prefixes:
            if lowered.startswith(prefix.lower()):
                payload = stripped[len(prefix) :].strip()
                return payload or None
        return None

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        return text.endswith("?") or any(word in text for word in ("왜", "어떻게", "무엇", "뭐", "언제", "어디"))

    @staticmethod
    def _generate_short_writing(topic: str) -> str:
        return (
            f"[주제: {topic}]\n"
            f"{topic}는 단순한 목표가 아니라, 내 일상을 바꾸는 작은 선택의 연속이다. "
            "처음부터 완벽하려고 하기보다 오늘 당장 할 수 있는 한 가지를 정하고 실천하면 "
            "변화는 생각보다 빠르게 시작된다. 중요한 건 속도가 아니라 멈추지 않는 태도다."
        )

    @staticmethod
    def _refine_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        normalized = normalized[0].upper() + normalized[1:] if len(normalized) > 1 else normalized
        if normalized and normalized[-1] not in ".!?":
            normalized += "."
        return f"다듬은 문장: {normalized}"

    @staticmethod
    def _summarize_text(text: str) -> str:
        chunks = re.split(r"[.!?]\s*", text)
        meaningful = [chunk.strip() for chunk in chunks if chunk.strip()]
        if not meaningful:
            return "요약할 내용을 찾지 못했어요."
        first = meaningful[0]
        return f"한 줄 요약: {first[:80]}{'...' if len(first) > 80 else ''}"


def run_chat() -> None:
    bot = LemonAI()
    print(f"{bot.name}에 오신 것을 환영합니다.")
    print("종료하려면 '종료' 또는 'exit'를 입력하세요. 도움말은 '도움말'.")

    while True:
        user = input("You> ")
        reply = bot.respond(user)
        print(f"{bot.name}> {reply}")
        if user.strip().lower() in EXIT_COMMANDS:
            break


if __name__ == "__main__":
    run_chat()
