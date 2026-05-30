import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from i18n import t


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
                r"(?:\b|[\W_])(?:ignore|disregard|forget|override|bypass|negate|overwrite|cancel|stop|bỏ qua|quên|xóa|vô hiệu|無視して|忘れて|上書き|キャンセル)\b"
                r".{0,100}\b(?:previous|prior|above|earlier|all|original|system|baseline|trước đó|cũ|ban đầu|hệ thống|以前の|元の|システム)\b"
                r".{0,100}\b(?:instructions?|rules?|system prompt|guardrails?|guidelines?|constraints?|lệnh|quy tắc|hướng dẫn|ràng buộc|指示|ルール|プロンプト|制約)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "act_as_system_or_developer",
            re.compile(
                r"(?:\b|[\W_])(?:act|behave|pretend|mimic|roleplay|simulate|đóng vai|hành xử|giả vờ|làm|演じて|ふりをして|なりきって|シミュレート)\b"
                r".{0,60}\b(?:as|like|the role of|như|vai trò|として|のように|役割)\b"
                r".{0,60}\b(?:system|developer|admin(?:istrator)?|root|god|kernel|super-user|technical support|hệ thống|lập trình viên|quản trị viên|システム|開発者|管理者)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "disable_safety",
            re.compile(
                r"(?:\b|[\W_])(?:disable|turn off|remove|skip|bypass|disable|suspend|deactivate|tắt|vô hiệu hóa|bỏ qua|xóa|無効にして|オフにして|解除|停止)\b"
                r".{0,60}\b(?:safety|policy|guardrails?|filters?|censorship|moderation|protections?|an toàn|bảo vệ|chính sách|kiểm duyệt|bộ lọc|安全|ポリシー|フィルター|検閲|保護)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "role_spoofing_header",
            re.compile(
                r"^\s*(?:system|developer|assistant|user|admin|hệ thống|lập trình viên|システム|開発者|アシスタント)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "jailbreak_mode",
            re.compile(
                r"\b(?:jailbreak|dan mode|developer mode|aim mode|unfiltered mode|do anything now|broken constraints?|unshackled|free mode|chế độ không giới hạn|chế độ nhà phát triển|脱獄|開発者モード|制限なしモード|フリーモード|何でもできるモード)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "new_conversation_spoof",
            re.compile(
                r"(?:\b|[\W_])(?:end of conversation|new conversation|start fresh|reboot|initialize|reset session|bắt đầu lại|cuộc trò chuyện mới|xóa lịch sử|会話終了|新しい会話|リセット|セッション初期化|履歴削除)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "output_formatting_override",
            re.compile(
                r"(?:\b|[\W_])(?:output|respond|reply|format|print|trả lời|xuất|in ra)\b"
                r".{0,60}\b(?:only|exactly|using|in|as|chỉ|chính xác|bằng)\b"
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
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose|tell me|extract|what is|hiển thị|tiết lộ|in ra|cho tôi xem|đọc|見せて|表示して|出力して|教えて|抽出)\b"
                r".{0,120}\b(?:system|developer|hidden|internal|original|initial|base|underlying|hệ thống|ẩn|nội bộ|ban đầu|システム|隠された|内部|元の)\b"
                r".{0,120}\b(?:prompt|instructions?|message|rules?|personality|identity|logic|lệnh|quy tắc|hướng dẫn|プロンプト|指示|ルール|ロジック)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "request_markdown_source",
            re.compile(
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose|hiển thị|tiết lộ|in ra|cho tôi xem|đọc|見せて|表示して|出力して)\b"
                r".{0,100}\b(?:markdown|source|file|text|raw content|mã nguồn|văn bản thô|ソースコード|マークダウン|生テキスト)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "rules_file_probe",
            re.compile(
                r"\b(?:system_rules\.md|rules source|rules markdown|system rules|gemini\.md|luật hệ thống|システムルール|ルールファイル)\b",
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
        # Vietnamese additions
        "bạn là miku",
        # Japanese additions
        "あなたはmiku",
        "システムプロンプト",
        "内部ルール",
        "quy tắc hệ thống",
        "hướng dẫn nội bộ",
    )

    REPLY_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        (
            "system_prompt_dump",
            re.compile(
                r"^\s*(?:system|developer|assistant|hệ thống|lập trình viên|システム|開発者)\s*(?:prompt|instructions?|quy tắc|lệnh|プロンプト|指示)\s*:",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "internal_prompt_phrase",
            re.compile(
                r"(?:\b|[\W_])(?:internal|hidden|developer|baseline|nội bộ|ẩn|内部|隠された)\s+(?:prompt|instructions?|logic|rules?|quy tắc|lệnh|プロンプト|指示|ロジック|ルール)\b",
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
        logger_callback: Callable[[KomiFilterDecision, str], None] | None = None,
    ) -> None:
        self.enabled = enabled
        self.max_check_chars = max(256, max_check_chars)
        self.block_response_on_leak = block_response_on_leak
        self.logger_callback = logger_callback

    def inspect_user_prompt(self, text: str) -> KomiFilterDecision:
        if not self.enabled:
            return KomiFilterDecision(blocked=False)
        
        # Fast path for empty or very short strings
        if not text or len(text.strip()) < 3:
            return KomiFilterDecision(blocked=False)
            
        sample = self._prepare_text(text)
        if not sample:
            return KomiFilterDecision(blocked=False)

        # 1. Check for prompt injection
        injection_hits = self._collect_matches(sample, self.USER_INJECTION_PATTERNS)
        if injection_hits:
            decision = KomiFilterDecision(
                blocked=True,
                category="prompt_injection",
                reason="suspicious instruction override attempt",
                matches=injection_hits,
            )
            self._log(decision, text)
            return decision

        # 2. Check for prompt leak requests
        leak_hits = self._collect_matches(sample, self.USER_PROMPT_LEAK_PATTERNS)
        if leak_hits:
            decision = KomiFilterDecision(
                blocked=True,
                category="prompt_leak_request",
                reason="suspicious system prompt discovery attempt",
                matches=leak_hits,
            )
            self._log(decision, text)
            return decision

        return KomiFilterDecision(blocked=False)

    def inspect_model_reply(self, text: str) -> KomiFilterDecision:
        if not self.enabled or not self.block_response_on_leak:
            return KomiFilterDecision(blocked=False)
            
        # Fast path
        if not text:
            return KomiFilterDecision(blocked=False)
        
        sample = self._prepare_text(text)
        if not sample:
            return KomiFilterDecision(blocked=False)

        lowered = sample.lower()
        
        # 1. Search for literal markers of the system prompt or internal state (Fast substring check)
        strong_hits = tuple(
            marker for marker in self.REPLY_STRONG_LEAK_MARKERS if marker in lowered
        )
        if strong_hits:
            decision = KomiFilterDecision(
                blocked=True,
                category="prompt_leak_response",
                reason="model response exposed internal instruction markers",
                matches=strong_hits,
            )
            self._log(decision, text)
            return decision

        # 2. Check with patterns for structural leaks (Slower regex check)
        weak_hits = self._collect_matches(sample, self.REPLY_LEAK_PATTERNS)
        if weak_hits:
            decision = KomiFilterDecision(
                blocked=True,
                category="prompt_leak_response",
                reason="model response resembles an internal prompt dump",
                matches=weak_hits,
            )
            self._log(decision, text)
            return decision

        return KomiFilterDecision(blocked=False)

    def user_block_message(self, decision: KomiFilterDecision, locale: str | None = None) -> str:
        """Return a user-facing block message, localized."""
        category_to_key = {
            "prompt_injection": "komifilter.injection_blocked",
            "prompt_leak_request": "komifilter.leak_blocked",
        }
        key = category_to_key.get(decision.category or "", "komifilter.default_blocked")
        return t(key, locale)

    def reply_block_message(self, locale: str | None = None) -> str:
        """Return a reply-block message, localized."""
        return t("komifilter.response_blocked", locale)

    def _prepare_text(self, text: str) -> str:
        if not text:
            return ""
        
        # Truncate to avoid DoS on heavy regex (Performance)
        truncated = text[: self.max_check_chars]
        
        # Unicode normalization (NFC) to handle character-based bypasses
        # Convert to lower early for more consistent matching
        normalized = unicodedata.normalize("NFC", truncated)
        
        # Aggressively remove common obfuscation characters (Security)
        # Including zero-width spaces, soft hyphens, and various joiners
        cleaned = re.sub(r"[\u200b-\u200d\ufeff\u00ad\u2060-\u206f]", "", normalized)
        
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
        
    def _log(self, decision: KomiFilterDecision, original_text: str) -> None:
        if self.logger_callback:
            try:
                self.logger_callback(decision, original_text)
            except Exception:
                pass  # Do not let logging failure crash the filter

