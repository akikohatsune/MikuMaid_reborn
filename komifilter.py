import base64
import binascii
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
                r"(?:\b|[\W_])(?:ignore|disregard|forget|override|bypass|negate|overwrite|cancel|stop|bỏ qua|bo qua|quên|quen|xóa|xoa|vô hiệu|vo hieu|hủy bỏ|huy bo|無視して|忘れて|上書き|キャンセル)\b"
                r".{0,100}\b(?:previous|prior|above|earlier|all|original|system|baseline|trước đó|truoc do|cũ|cu|ban đầu|ban dau|hệ thống|he thong|mọi|moi|tất cả|tat ca|以前の|元の|システム)\b"
                r".{0,100}\b(?:instructions?|rules?|system prompt|guardrails?|guidelines?|constraints?|lệnh|lenh|quy tắc|quy tac|hướng dẫn|huong dan|ràng buộc|rang buoc|chỉ dẫn|chi dan|指示|ルール|プロンプト|制約)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "act_as_system_or_developer",
            re.compile(
                r"(?:\b|[\W_])(?:act|behave|pretend|mimic|roleplay|simulate|đóng vai|dong vai|hành xử|hanh xu|giả vờ|gia vo|làm|lam|演じて|ふりをして|なりきって|シミュレート)\b"
                r".{0,60}\b(?:as|like|the role of|như|nhu|vai trò|vai tro|として|のように|役割)\b"
                r".{0,60}\b(?:system|developer|admin(?:istrator)?|root|god|kernel|super-user|technical support|hệ thống|he thong|lập trình viên|lap trinh vien|quản trị viên|quan tri vien|システム|開発者|管理者)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "disable_safety",
            re.compile(
                r"(?:\b|[\W_])(?:disable|turn off|remove|skip|bypass|suspend|deactivate|tắt|tat|vô hiệu hóa|vo hieu hoa|bỏ qua|bo qua|gỡ bỏ|go bo|xóa|xoa|無効にして|オフにして|解除|停止)\b"
                r".{0,60}\b(?:safety|policy|guardrails?|filters?|censorship|moderation|protections?|ethics|an toàn|an toan|bảo vệ|bao ve|chính sách|chinh sach|kiểm duyệt|kiem duyet|bộ lọc|bo loc|đạo đức|dao duc|安全|ポリシー|フィルター|検閲|保護|倫理)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "special_tokens_or_delimiters",
            re.compile(
                r"(?:<\|im_start\|>|<\|im_end\|>|<\|system\|>|<\|assistant\|>|<\|user\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|\[(?:SYSTEM|DEVELOPER|ADMIN)(?:\s+PROMPT)?\]|```(?:system|developer|instructions))",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "role_spoofing_header",
            re.compile(
                r"^\s*(?:system|developer|assistant|admin|hệ thống|he thong|lập trình viên|lap trinh vien|quản trị viên|quan tri vien|システム|開発者|アシスタント)\s*:\s*(?:you are|ignore|override|bạn là|ban la|bỏ qua|bo qua|指示|設定)",
                flags=re.IGNORECASE | re.MULTILINE,
            ),
        ),
        (
            "jailbreak_mode",
            re.compile(
                r"\b(?:jailbreak|dan mode|developer mode|aim mode|unfiltered mode|godmode|stan mode|dude mode|anti-?gpt|chaos-?gpt|broken constraints?|unshackled|free mode|chế độ không giới hạn|che do khong gioi han|chế độ nhà phát triển|che do nha phat trien|chế độ bẻ khóa|che do be khoa|chế độ tự do|che do tu do)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "japanese_injection_and_jailbreak",
            re.compile(
                r"(?:これまでの|以前の|元の|システム|過去の|全ての|すべての).{0,40}(?:指示|ルール|プロンプト|ガイドライン).{0,40}(?:無視|忘れ|無効|解除|破棄|キャンセル)|(?:指示|ルール|プロンプト).{0,20}(?:無視|忘れ|無効|解除)|(?:脱獄|ジェイルブレイク|開発者モード|制限(?:なし|解除)モード|何でもできるモード)",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "hypothetical_unrestricted_roleplay",
            re.compile(
                r"(?:\b|[\W_])(?:in a hypothetical|hypothetically speaking|pretend you have no|imagine you are completely unrestricted|fictional universe where (?:safety|rules)|tưởng tượng bạn là (?:ai|robot) không có (?:giới hạn|luật lệ)|tuong tuong ban la (?:ai|robot) khong co (?:gioi han|luat le)|giả sử trong một thế giới không có quy tắc|gia su trong mot the gioi khong co quy tac|架空の世界ではルールがなく|何の制約もないと仮定して)\b",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "completion_forcing",
            re.compile(
                r"(?:\b|[\W_])(?:start your (?:response|reply) with|you must begin by saying|bắt đầu câu trả lời (?:của bạn )?bằng|bat dau cau tra loi (?:cua ban )?bang|hãy trả lời bắt đầu bằng|hay tra loi bat dau bang|必ず「.{1,30}」から始めて)\b"
                r".{0,60}\b(?:sure|here (?:are|is)|understood|dưới đây là|duoi day la|chắc chắn rồi|chac chan roi|承知しました)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "new_conversation_spoof",
            re.compile(
                r"(?:\b|[\W_])(?:end of conversation|new conversation|start fresh|reboot session|initialize new session|reset session|bắt đầu lại cuộc trò chuyện|bat dau lai cuoc tro chuyen|cuộc trò chuyện mới|cuoc tro chuyen moi|xóa lịch sử phiên|xoa lich su phien|会話終了|新しい会話|リセット|セッション初期化|履歴削除)\b",
                flags=re.IGNORECASE,
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
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose|tell me|extract|what is|hiển thị|hien thi|tiết lộ|tiet lo|in ra|cho tôi xem|cho toi xem|đọc|doc|cho biết|cho biet|见せて|表示して|出力して|教えて|抽出)\b"
                r".{0,120}\b(?:system|developer|hidden|internal|original|initial|base|underlying|raw|hệ thống|he thong|ẩn|an|nội bộ|noi bo|ban đầu|ban dau|gốc|goc|システム|隠された|内部|元の)\b"
                r".{0,120}\b(?:prompt|instructions?|message|rules?|personality|identity|logic|guidelines|lệnh|lenh|quy tắc|quy tac|hướng dẫn|huong dan|chỉ thị|chi thi|プロンプト|指示|ルール|ロジック)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "request_system_prompt_ja",
            re.compile(
                r"(?:システムプロンプト|システムルール|内部ルール|内部指示|指示書|ルールファイル).{0,40}(?:見せて|表示|出力|教えて|公開|抽出)",
                flags=re.IGNORECASE,
            ),
        ),
        (
            "repeat_verbatim_probe",
            re.compile(
                r"(?:\b|[\W_])(?:repeat|output|recite|spell out|nhắc lại|nhac lai|đọc lại|doc lai|nói lại|noi lai|繰り返して)\b"
                r".{0,80}\b(?:verbatim|word for word|all text above|everything above|từng từ một|tung tu mot|toàn bộ văn bản ở trên|toan bo van ban o tren|tất cả chữ ở trên|tat ca chu o tren|上記のすべて|一字一句)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "request_markdown_source",
            re.compile(
                r"(?:\b|[\W_])(?:show|reveal|print|dump|display|repeat|quote|return|expose|hiển thị|hien thi|tiết lộ|tiet lo|in ra|cho tôi xem|cho toi xem|đọc|doc|見せて|表示して|出力して)\b"
                r".{0,100}\b(?:markdown|source|raw content|mã nguồn|ma nguon|văn bản thô|van ban tho|nội dung file markdown|noi dung file markdown|ソースコード|マークダウン|生テキスト)\b",
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ),
        (
            "rules_file_probe",
            re.compile(
                r"\b(?:system_rules\.md|rules source|rules markdown|system rules|gemini\.md|miku response rules|critical language rule|luật hệ thống|luat he thong|quy tắc hệ thống|quy tac he thong|システムルール|ルールファイル)\b",
                flags=re.IGNORECASE,
            ),
        ),
    )

    # --- Strong Model Leak Markers (Filtered from Model Response) ---
    REPLY_STRONG_LEAK_MARKERS: tuple[str, ...] = (
        "you must follow these extra system rules loaded from markdown",
        "rules source:",
        "rules markdown:",
        "# miku response rules",
        "critical language rule",
        "for math answers, do not use latex delimiters",
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
        "quy tắc hệ thống",
        "hướng dẫn nội bộ",
        # Japanese additions
        "あなたはmiku",
        "システムプロンプト",
        "内部ルール",
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

        # Build candidate inspection variants (raw normalized, despaced, unaccented, decoded b64)
        candidates: list[str] = [sample]
        despaced = self._despace_text(sample)
        if despaced and despaced != sample:
            candidates.append(despaced)

        unaccented = self._strip_accents(sample)
        if unaccented and unaccented != sample:
            candidates.append(unaccented)

        if despaced:
            despaced_unaccented = self._strip_accents(despaced)
            if despaced_unaccented and despaced_unaccented not in candidates:
                candidates.append(despaced_unaccented)

        b64_payloads = self._extract_and_decode_base64(sample)
        if b64_payloads:
            for payload in b64_payloads:
                candidates.append(payload)
                payload_unaccented = self._strip_accents(payload)
                if payload_unaccented != payload:
                    candidates.append(payload_unaccented)

        for candidate in candidates:
            # 1. Check for prompt injection
            injection_hits = self._collect_matches(candidate, self.USER_INJECTION_PATTERNS)
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
            leak_hits = self._collect_matches(candidate, self.USER_PROMPT_LEAK_PATTERNS)
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
        
        # Unicode normalization (NFKC) to resolve fullwidth and compatibility characters
        normalized = unicodedata.normalize("NFKC", truncated)
        
        # Aggressively remove common obfuscation & invisible control characters (Security)
        cleaned = re.sub(
            r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufe00-\ufe0f\ufeff\u00ad\u034f\u180e]",
            "",
            normalized,
        )
        
        return cleaned.strip()

    def _despace_text(self, text: str) -> str:
        """Collapse single characters separated by whitespace or punctuation (e.g. 'i g n o r e' -> 'ignore')."""
        if not text:
            return ""
        parts = re.split(r"(\s{2,})", text)
        cleaned_parts: list[str] = []
        for part in parts:
            if not part.strip():
                cleaned_parts.append(" ")
                continue
            words = part.split()
            res: list[str] = []
            buf: list[str] = []
            for w in words:
                if len(w) == 1 and w.isalnum():
                    buf.append(w)
                else:
                    if buf:
                        res.append("".join(buf) if len(buf) > 1 else buf[0])
                        buf = []
                    res.append(w)
            if buf:
                res.append("".join(buf) if len(buf) > 1 else buf[0])
            cleaned_parts.append(" ".join(res))
        return " ".join(cleaned_parts)

    def _strip_accents(self, text: str) -> str:
        """Remove Vietnamese and Latin diacritical accents for unaccented matching."""
        if not text:
            return ""
        de_d = text.replace("đ", "d").replace("Đ", "D")
        return "".join(
            c for c in unicodedata.normalize("NFD", de_d) if unicodedata.category(c) != "Mn"
        )

    def _extract_and_decode_base64(self, text: str) -> list[str]:
        """Detect and decode potential base64 encoded injection payloads."""
        candidates = re.findall(r"[A-Za-z0-9+/]{20,}={0,2}", text)
        decoded_results: list[str] = []
        for cand in candidates:
            try:
                raw_bytes = base64.b64decode(cand, validate=True)
                decoded_text = raw_bytes.decode("utf-8", errors="ignore").strip()
                if len(decoded_text) >= 5 and any(c.isalpha() for c in decoded_text):
                    decoded_results.append(self._prepare_text(decoded_text))
            except Exception:
                continue
        return decoded_results

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

