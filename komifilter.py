import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class KomiFilterDecision:
    blocked: bool
    category: str | None = None
    reason: str | None = None
    matches: tuple[str, ...] = ()


class KomiFilter:
    # --- Advanced Prompt Injection Patterns ---
    USER_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "ignore_previous_instructions",
            re.compile(
                r"(?:\b|[\W_])(?:ignore|disregard|forget|override|bypass|negate|overwrite|cancel|stop)\b"
                r".{0,100}\b(?:previous|prior|above|earlier|all|original|system|baseline)\b"
                r".{0,100}\b(?:instructions?|rules?|system prompt|guardrails?|guidelines?|constraints?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "act_as_system_or_developer",
            re.compile(
                r"(?:\b|[\W_])(?:act|behave|pretend|mimic|roleplay|simulate)\b"
                r".{0,60}\b(?:as|like|the role of)\b"
                r".{0,60}\b(?:system|developer|admin(?:istrator)?|root|god|kernel|super-user|technical support)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "disable_safety",
            re.compile(
                r"(?:\b|[\W_])(?:disable|turn off|remove|skip|bypass|disable|suspend|deactivate)\b"
                r".{0,60}\b(?:safety|policy|guardrails?|filters?|censorship|moderation|protections?)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "role_spoofing_header",
            re.compile(
                r"^\s*(?:system|developer|assistant|user|admin)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "jailbreak_mode",
            re.compile(
                r"\b(?:jailbreak|dan mode|developer mode|aim mode|unfiltered mode|do anything now|broken constraints?|unshackled|free mode)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "new_conversation_spoof",
            re.compile(
                r"(?:\b|[\W_])(?:end of conversation|new conversation|start fresh|reboot|initialize|reset session)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "output_formatting_override",
            re.compile(
                r"(?:\b|[\W_])(?:output|respond|reply|format|print)\b"
                r".{0,60}\b(?:only|exactly|using|in|as)\b"
                r".{0,60}\b(?:json|code|raw|markdown|hex|base64|binary|python|terminal|shell)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "obfuscation_payload",
            re.compile(
                r"(?:(?:\\x[0-9a-f]{2}){4,}|(?:\\u[0-9a-f]{4}){3,}|(?:&#x?[0-9a-f]+;){4,})",
                flags=re.IGNORECASE,
            ),
        ),
    )

    # --- Prompt Leak Prevention Patterns ---
    USER_PROMPT_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "request_system_prompt",
            re.compile(
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose|tell me|extract|what is)\b"
                r".{0,120}\b(?:system|developer|hidden|internal|original|initial|base|underlying)\b"
                r".{0,120}\b(?:prompt|instructions?|message|rules?|personality|identity|logic)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "request_markdown_source",
            re.compile(
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose)\b"
                r".{0,100}\b(?:markdown|source|file|text|raw content)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "rules_file_probe",
            re.compile(
                r"\b(?:system_rules\.md|rules source|rules markdown|system rules|gemini\.md)\b",
                flags=re.IGNORECASE,
            ),
        ),
    )

    # --- Strong Model Leak Markers (Filtered from Model Response) ---
    REPLY_STRONG_LEAK_MARKERS: tuple[str, ...] = (
        "you must follow these extra system rules loaded from markdown",
        "rules source:",
        "rules markdown:",
        "[call_profile_context]",
        "[message_content]",
        "[hidden_hook:miku_fear]",
        "[attached_images=",
        "user calls miku:",
        "miku calls user:",
        "you are miku, a playful ai assistant on discord",
        "default to english unless the user explicitly asks",
    )

    REPLY_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "system_prompt_dump",
            re.compile(
                r"^\s*(?:system|developer|assistant)\s*(?:prompt|instructions?)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "internal_prompt_phrase",
            re.compile(
                r"(?:\b|[\W_])(?:internal|hidden|developer|baseline)\s+(?:prompt|instructions?|logic|rules?)\b",
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

        # 1. Check for prompt injection
        injection_hits = self._collect_matches(sample, self.USER_INJECTION_PATTERNS)
        if injection_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_injection",
                reason="suspicious instruction override attempt",
                matches=injection_hits,
            )

        # 2. Check for prompt leak requests
        leak_hits = self._collect_matches(sample, self.USER_PROMPT_LEAK_PATTERNS)
        if leak_hits:
            return KomiFilterDecision(
                blocked=True,
                category="prompt_leak_request",
                reason="suspicious system prompt discovery attempt",
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
        
        # 1. Search for literal markers of the system prompt or internal state
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

        # 2. Check with patterns for structural leaks
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
                "komifilter! phát hiện nỗ lực thay đổi quy tắc hệ thống. "
                "vui lòng đặt câu hỏi trực tiếp mà không cố gắng bỏ qua các ràng buộc."
            )
        return (
            "komifilter! phát hiện yêu cầu rò rỉ thông tin nội bộ. "
            "tôi không được phép tiết lộ quy tắc hoặc hướng dẫn hệ thống."
        )

    def reply_block_message(self) -> str:
        return (
            "komifilter! nội dung phản hồi bị chặn vì chứa thông tin nhạy cảm của hệ thống. "
            "vui lòng thử lại với một yêu cầu khác."
        )

    def _prepare_text(self, text: str) -> str:
        if not text:
            return ""
        
        # Truncate to avoid DoS on heavy regex
        truncated = text[: self.max_check_chars]
        
        # Unicode normalization (NFC) to handle character-based bypasses (e.g. e + accent)
        normalized = unicodedata.normalize("NFC", truncated)
        
        # Remove common obfuscation characters like zero-width spaces, etc.
        cleaned = re.sub(r"[\u200b-\u200d\ufeff\u00ad]", "", normalized)
        
        return cleaned.strip()

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

