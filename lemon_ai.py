#!/usr/bin/env python3
"""Lemon AI: 대화 맥락을 따라가는 콘솔 AI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re


EXIT_COMMANDS = {"종료", "exit", "quit", "bye", "그만"}


@dataclass
class LemonAI:
    """대화 맥락을 저장하고 응답/글쓰기를 수행하는 챗봇."""

    name: str = "Lemon AI"
    memory: list[str] = field(default_factory=list)
    active_topic: str = ""

    def respond(self, message: str) -> str:
        cleaned = message.strip()
        if not cleaned:
            return "아무 말도 입력되지 않았어요. 한 문장만 편하게 적어주세요."

        self.memory.append(cleaned)
        lowered = cleaned.lower()

        if lowered in EXIT_COMMANDS:
            return "대화를 마칠게요. 다음에 또 만나요!"

        if "도움말" in cleaned or lowered == "help":
            return (
                "할 수 있는 것들:\n"
                "1) 대화: 고민/질문을 자연스럽게 이어서 답변\n"
                "2) 글쓰기: '글써줘: 주제'\n"
                "3) 다듬기: '다듬어: 문장'\n"
                "4) 요약: '요약: 긴 문장'\n"
                "5) 이어서 진행: '계속'"
            )

        if lowered == "계속":
            return self._continue_topic()

        writing_topic = self._extract_writing_topic(cleaned)
        if writing_topic:
            self.active_topic = writing_topic
            return self._generate_short_writing(writing_topic)

        refine_text = self._extract_payload(cleaned, prefixes=("다듬어:", "교정:", "고쳐줘:"))
        if refine_text:
            self.active_topic = "문장 다듬기"
            return self._refine_text(refine_text)

        summary_text = self._extract_payload(cleaned, prefixes=("요약:", "정리:", "한줄요약:"))
        if summary_text:
            self.active_topic = "요약"
            return self._summarize_text(summary_text)

        if "이름" in cleaned or "누구" in cleaned:
            return f"저는 {self.name}예요. 대화 맥락을 이어서 이야기하는 걸 잘해요."

        if "시간" in cleaned or "몇 시" in cleaned:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            return f"지금 시간은 {now}입니다."

        if len(self.memory) > 1 and ("기억" in cleaned or "방금" in cleaned):
            previous = self.memory[-2]
            return f"직전에 '{previous}'라고 말해주셨어요. 그 흐름으로 이어가볼까요?"

        emotion = self._detect_emotion(cleaned)
        if emotion:
            return self._emotion_reply(emotion, cleaned)

        if self._looks_like_question(cleaned):
            self.active_topic = self._guess_topic(cleaned)
            return self._question_reply(cleaned)

        self.active_topic = self._guess_topic(cleaned)
        return self._contextual_reply(cleaned)

    def _continue_topic(self) -> str:
        if not self.active_topic and len(self.memory) < 2:
            return "이어서 진행할 주제가 아직 없어요. 먼저 고민이나 주제를 한 줄로 알려주세요."
        topic = self.active_topic or self._guess_topic(self.memory[-2])
        return (
            f"좋아요, '{topic}' 주제로 이어갈게요.\n"
            "- 지금 상태를 1문장으로 정리\n"
            "- 가장 막히는 지점 1개\n"
            "- 오늘 바로 할 행동 1개\n"
            "이렇게 보내주면 제가 다음 답을 딱 맞게 이어서 드릴게요."
        )

    def _question_reply(self, text: str) -> str:
        topic = self.active_topic or self._guess_topic(text)
        return (
            f"좋은 질문이에요. 핵심 주제는 '{topic}'로 보이네요.\n"
            "원하면 ①빠른 답 ②자세한 설명 ③실행 계획 중 원하는 형식으로 바로 답해드릴게요."
        )

    def _contextual_reply(self, text: str) -> str:
        topic = self.active_topic or self._guess_topic(text)
        return (
            f"말씀하신 내용을 '{topic}' 관점으로 이해했어요.\n"
            "원하시면 제가 지금 문장을 더 명확하게 다듬거나, 바로 실행 계획 3단계로 바꿔드릴게요."
        )

    def _detect_emotion(self, text: str) -> str | None:
        if re.search(r"(힘들|우울|슬프|지쳤|불안|답답)", text):
            return "negative"
        if re.search(r"(좋아|행복|신나|기뻐|잘됐|성공)", text):
            return "positive"
        return None

    def _emotion_reply(self, emotion: str, text: str) -> str:
        topic = self._guess_topic(text)
        self.active_topic = topic
        if emotion == "negative":
            return (
                "많이 버거우셨겠어요. 괜찮아요, 하나씩 정리해봐요.\n"
                f"지금은 '{topic}'에서 가장 힘든 한 가지를 말해주시면, 바로 해결 순서를 잡아드릴게요."
            )
        return (
            "좋은 흐름이에요! 이 momentum을 유지하는 게 중요해요.\n"
            f"'{topic}' 관련해서 오늘 마무리할 한 가지를 정하면 제가 문장/계획으로 정리해드릴게요."
        )

    def _guess_topic(self, text: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z가-힣\s]", " ", text)
        tokens = [self._strip_particle(t) for t in cleaned.split() if len(t) >= 2]
        stopwords = {
            "저", "저는", "제가", "그냥", "진짜", "너무", "이거", "저거", "오늘", "내일", "요즘", "이제", "계속",
            "어떻게", "무엇", "뭐", "왜", "언제", "어디", "관련", "대한", "하고", "하는", "에서", "하면",
            "답답해", "힘들어", "불안해", "우울해", "좋아", "기뻐",
        }
        keywords = [t for t in tokens if t and t not in stopwords]
        if not keywords:
            return "현재 고민"
        keywords.sort(key=len, reverse=True)
        return keywords[0]

    @staticmethod
    def _strip_particle(token: str) -> str:
        particles = ("은", "는", "이", "가", "을", "를", "에", "에서", "으로", "와", "과", "도", "만", "요")
        for particle in particles:
            if token.endswith(particle) and len(token) > len(particle):
                return token[: -len(particle)]
        return token

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
            f"{topic}는 거창한 결심보다 작고 반복 가능한 실천에서 시작된다. "
            "완벽함을 기다리기보다 오늘 가능한 최소 행동을 정하면, 내일의 부담은 줄고 자신감은 쌓인다. "
            "결국 변화를 만드는 건 재능이 아니라 꾸준히 돌아오는 태도다."
        )

    @staticmethod
    def _refine_text(text: str) -> str:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return "다듬을 문장이 비어 있어요."
        if normalized[-1] not in ".!?":
            normalized += "."
        return f"다듬은 문장: {normalized}"

    @staticmethod
    def _summarize_text(text: str) -> str:
        chunks = re.split(r"[.!?]\s*", text)
        meaningful = [chunk.strip() for chunk in chunks if chunk.strip()]
        if not meaningful:
            return "요약할 내용을 찾지 못했어요."
        first = meaningful[0]
        return f"한 줄 요약: {first[:90]}{'...' if len(first) > 90 else ''}"


def run_chat() -> None:
    bot = LemonAI()
    print(f"{bot.name}에 오신 것을 환영합니다.")
    print("종료하려면 '종료' 또는 'exit'. 도움말은 '도움말'.")

    while True:
        user = input("You> ")
        reply = bot.respond(user)
        print(f"{bot.name}> {reply}")
        if user.strip().lower() in EXIT_COMMANDS:
            break


if __name__ == "__main__":
    run_chat()
