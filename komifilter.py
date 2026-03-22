from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class KomiFilterDecision:
    blocked: bool
    category: str | None = None
    reason: str | None = None
    matches: tuple[str, ...] = ()


class KomiFilter:
    USER_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "ignore_previous_instructions",
            re.compile(
                r"\b(?:ignore|disregard|forget|override|bypass)\b.{0,80}\b"
                r"(?:previous|prior|above|earlier|all)\b.{0,80}\b"
                r"(?:instructions?|rules?|system prompt|guardrails?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "act_as_system_or_developer",
            re.compile(
                r"\b(?:act|behave|pretend)\b.{0,40}\b(?:as|like)\b.{0,40}\b"
                r"(?:system|developer|admin(?:istrator)?|root)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "disable_safety",
            re.compile(
                r"\b(?:disable|turn off|remove|skip)\b.{0,40}\b"
                r"(?:safety|policy|guardrails?|filters?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "role_spoofing_header",
            re.compile(
                r"^\s*(?:system|developer)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "jailbreak_mode",
            re.compile(
                r"\b(?:jailbreak|dan mode|developer mode)\b",
                flags=re.IGNORECASE,
            ),
        ),
    )
    USER_PROMPT_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "request_system_prompt",
            re.compile(
                r"\b(?:show|reveal|print|dump|display|repeat|quote|return|expose)\b"
                r".{0,80}\b(?:system|developer|hidden|internal)\b.{0,80}\b"
                r"(?:prompt|instructions?|message|rules?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "ask_direct_system_prompt",
            re.compile(
                r"\b(?:what(?:'s| is)|where(?:'s| is)|tell me)\b.{0,60}\b"
                r"(?:your|the)\b.{0,20}\b(?:system|developer)\b.{0,20}\b"
                r"(?:prompt|instructions?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "rules_file_probe",
            re.compile(
                r"\b(?:system_rules\.md|rules source|rules markdown)\b",
                flags=re.IGNORECASE,
            ),
        ),
    )
    REPLY_STRONG_LEAK_MARKERS: tuple[str, ...] = (
        "you must follow these extra system rules loaded from markdown",
        "rules source:",
        "rules markdown:",
        "[call_profile_context]",
        "[message_content]",
        "[hidden_hook:miku_fear]",
    )
    REPLY_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "system_prompt_dump",
            re.compile(
                r"^\s*(?:system|developer)\s*(?:prompt|instructions?)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "internal_prompt_phrase",
            re.compile(
                r"\b(?:internal|hidden|developer)\s+(?:prompt|instructions?)\b",
                flags=re.IGNORECASE,
            ),
        ),
    )

    def __init__(
        self,
        *,
        enabled: bool,
        max_check_chars: int,
        block_response_on_leak: bool,
    ) -> None:
        self.enabled = enabled
        self.max_check_chars = max(256, max_check_chars)
        self.block_response_on_leak = block_response_on_leak

    def inspect_user_prompt(self, text: str) -> KomiFilterDecision:
        if not self.enabled:
            return KomiFilterDecision(blocked=False)
        sample = self._prepare_text(text)
        if not sample:
            return KomiFilterDecision(blocked=False)

        injection_hits = self._collect_matches(sample, self.USER_INJECTION_PATTERNS)
        if injection_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_injection",
                reason="instruction override attempt",
                matches=injection_hits,
            )

        leak_hits = self._collect_matches(sample, self.USER_PROMPT_LEAK_PATTERNS)
        if leak_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_leak_request",
                reason="prompt leak request",
                matches=leak_hits,
            )

        return KomiFilterDecision(blocked=False)

    def inspect_model_reply(self, text: str) -> KomiFilterDecision:
        if not self.enabled or not self.block_response_on_leak:
            return KomiFilterDecision(blocked=False)
        sample = self._prepare_text(text)
        if not sample:
            return KomiFilterDecision(blocked=False)

        lowered = sample.lower()
        strong_hits = tuple(
            marker for marker in self.REPLY_STRONG_LEAK_MARKERS if marker in lowered
        )
        if strong_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_leak_response",
                reason="model response exposed internal instruction markers",
                matches=strong_hits,
            )

        weak_hits = self._collect_matches(sample, self.REPLY_LEAK_PATTERNS)
        if weak_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_leak_response",
                reason="model response resembles an internal prompt dump",
                matches=weak_hits,
            )

        return KomiFilterDecision(blocked=False)

    def user_block_message(self, decision: KomiFilterDecision) -> str:
        if decision.category == "prompt_injection":
            return (
                "komifilter! blocked instruction-override attempt. "
                "Ask your actual task directly without trying to change system rules."
            )
        return (
            "komifilter! blocked prompt-leak request. "
            "I cannot reveal internal or system instructions."
        )

    def reply_block_message(self) -> str:
        return (
            "komifilter! internal prompt-like output was filtered. "
            "Please retry with a direct task request."
        )

    def _prepare_text(self, text: str) -> str:
        if not text:
            return ""
        return text[: self.max_check_chars].strip()

    def _collect_matches(
        self,
        text: str,
        rules: tuple[tuple[str, re.Pattern[str]], ...],
    ) -> tuple[str, ...]:
        found: list[str] = []
        for label, pattern in rules:
            if pattern.search(text):
                found.append(label)
        return tuple(found)

