from __future__ import annotations

from typing import Literal

AUTO_THEME = "auto"
FALLBACK_THEME = "ansi-dark"
DEFAULT_THEME = AUTO_THEME
DEFAULT_LOG_LEVEL = "WARNING"

type AudioClient = Literal["mistral"]
type ThinkingLevel = Literal["off", "low", "medium", "high", "max"]
type ThinkingMode = ThinkingLevel | Literal["auto"]
THINKING_LEVELS: tuple[ThinkingMode, ...] = (
    "off",
    "low",
    "medium",
    "high",
    "max",
    "auto",
)

type TranscriptionEncoding = Literal["pcm_s16le"]
type SpeechOutputFormat = Literal["pcm", "wav", "mp3", "flac", "opus"]
