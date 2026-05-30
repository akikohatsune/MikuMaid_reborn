"""Internationalization (i18n) engine for MikuMaid_reborn.

Provides automatic language detection, locale-aware message lookup,
and per-user language preference persistence.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection — uses `langdetect` if installed, falls back to heuristics
# ---------------------------------------------------------------------------
_LANGDETECT_AVAILABLE = False
try:
    from langdetect import detect as _ld_detect
    from langdetect import LangDetectException
    _LANGDETECT_AVAILABLE = True
except ImportError:
    pass


# Supported UI locales (bot system messages).
# LLM responses are NOT limited to these — the LLM can reply in any language.
SUPPORTED_LOCALES: tuple[str, ...] = ("en", "vi", "ja")
DEFAULT_LOCALE = "en"

# Map langdetect codes to our supported locales
_LANG_CODE_MAP: dict[str, str] = {
    "en": "en",
    "vi": "vi",
    "ja": "ja",
    # Common langdetect outputs that map to our supported locales
    "zh-cn": "en",  # Chinese → fallback to English
    "zh-tw": "en",
    "ko": "en",     # Korean → fallback to English
    "fr": "en",
    "de": "en",
    "es": "en",
    "pt": "en",
    "ru": "en",
    "th": "en",
    "id": "en",     # Indonesian
    "ms": "en",     # Malay
    "tl": "en",     # Tagalog
}


def detect_language(text: str) -> str:
    """Detect language from text, returning a supported locale code.

    Falls back to DEFAULT_LOCALE if detection fails or the language
    is not in our supported UI locales.
    """
    if not text or len(text.strip()) < 5:
        return DEFAULT_LOCALE

    # Try langdetect first
    if _LANGDETECT_AVAILABLE:
        try:
            detected = _ld_detect(text)
            mapped = _LANG_CODE_MAP.get(detected, DEFAULT_LOCALE)
            return mapped if mapped in SUPPORTED_LOCALES else DEFAULT_LOCALE
        except LangDetectException:
            pass

    # Heuristic fallback — check for Vietnamese and Japanese characters
    return _heuristic_detect(text)


def _heuristic_detect(text: str) -> str:
    """Simple heuristic language detection based on character ranges."""
    vi_chars = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ")
    jp_ranges = [
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x4E00, 0x9FFF),  # CJK Unified (shared with Chinese, but combined with kana → Japanese)
    ]

    vi_count = 0
    jp_count = 0

    for ch in text.lower():
        if ch in vi_chars:
            vi_count += 1
        code = ord(ch)
        for start, end in jp_ranges:
            if start <= code <= end:
                jp_count += 1
                break

    total = len(text)
    if total == 0:
        return DEFAULT_LOCALE

    vi_ratio = vi_count / total
    jp_ratio = jp_count / total

    if vi_ratio > 0.05:
        return "vi"
    if jp_ratio > 0.1:
        return "ja"

    return DEFAULT_LOCALE


class I18n:
    """Locale-aware message lookup with JSON-based locale files."""

    def __init__(self, locales_dir: str | Path | None = None) -> None:
        if locales_dir is None:
            locales_dir = Path(__file__).parent / "locales"
        self._locales_dir = Path(locales_dir)
        self._translations: dict[str, dict[str, Any]] = {}
        self._load_all_locales()

    def _load_all_locales(self) -> None:
        """Load all .json locale files from the locales directory."""
        if not self._locales_dir.exists():
            LOGGER.warning("Locales directory not found: %s", self._locales_dir)
            return

        for locale_file in self._locales_dir.glob("*.json"):
            locale_code = locale_file.stem
            try:
                with open(locale_file, "r", encoding="utf-8") as f:
                    self._translations[locale_code] = json.load(f)
                LOGGER.info("Loaded locale: %s", locale_code)
            except (json.JSONDecodeError, OSError) as exc:
                LOGGER.error("Failed to load locale %s: %s", locale_code, exc)

    def t(self, key: str, locale: str | None = None, **kwargs: Any) -> str:
        """Look up a translated string by dotted key path.

        Args:
            key: Dotted key path, e.g. "chat.banned_message"
            locale: Locale code (e.g. "vi", "en", "ja").
                    Falls back to DEFAULT_LOCALE if not found.
            **kwargs: Interpolation variables for str.format()

        Returns:
            The translated string, or the key itself if not found.
        """
        locale = locale or DEFAULT_LOCALE

        # Try requested locale first, then fall back to DEFAULT_LOCALE
        for try_locale in (locale, DEFAULT_LOCALE):
            if try_locale not in self._translations:
                continue
            value = self._resolve_key(self._translations[try_locale], key)
            if value is not None:
                try:
                    return value.format(**kwargs) if kwargs else value
                except (KeyError, IndexError, ValueError):
                    return value

        # Key not found in any locale — return the key itself as fallback
        LOGGER.warning("Missing i18n key: %s (locale=%s)", key, locale)
        return key

    def _resolve_key(self, data: dict[str, Any], key: str) -> str | None:
        """Resolve a dotted key path like 'chat.banned_message'."""
        parts = key.split(".")
        current: Any = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
            if current is None:
                return None
        return str(current) if current is not None else None

    def available_locales(self) -> list[str]:
        """Return list of loaded locale codes."""
        return sorted(self._translations.keys())


# ---------------------------------------------------------------------------
# Global singleton — initialized once, importable anywhere
# ---------------------------------------------------------------------------
_i18n_instance: I18n | None = None


def get_i18n() -> I18n:
    """Get or create the global I18n instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def t(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """Convenience function — shortcut for get_i18n().t(...)."""
    return get_i18n().t(key, locale, **kwargs)
