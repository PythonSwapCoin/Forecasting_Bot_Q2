"""
Lightweight logging utilities to capture run logs while keeping console noise low.

Console output is limited to errors and probability summaries; all other messages
are buffered for writing to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class RunLogger:
    """Collects log lines and selectively echoes important events to stdout."""

    buffer: List[str] = field(default_factory=list)
    entries: List[Tuple[str, str]] = field(default_factory=list)  # (level, message)
    search_counts: dict = field(default_factory=dict)
    serper_urls_attempted: int = 0
    serper_urls_success: int = 0
    echo_errors: bool = True
    echo_probabilities: bool = True
    echo_info: bool = False
    last_probability_line: str = ""

    def info(self, message: str) -> None:
        self.buffer.append(message)
        self.entries.append(("info", message))
        if self.echo_info:
            print(message)

    def error(self, message: str) -> None:
        line = f"[ERROR] {message}"
        self.buffer.append(line)
        self.entries.append(("error", message))
        if self.echo_errors:
            print(line)

    def probability(self, message: str) -> None:
        line = f"[PROBABILITY] {message}"
        if line == self.last_probability_line:
            return
        self.last_probability_line = line
        self.buffer.append(line)
        self.entries.append(("probability", message))
        if self.echo_probabilities:
            print(line)

    def log(self, message: str, level: str = "info") -> None:
        auto_level = level
        lowered = message.lower()
        if level == "info":
            if "[error" in lowered or "error:" in lowered:
                auto_level = "error"
            elif "[warn" in lowered:
                auto_level = "info"

        # Lightly parse search-related prefixes to capture counts
        if message.startswith("[Perplexity API]"):
            self.search_counts["perplexity"] = self.search_counts.get("perplexity", 0) + 1
        if message.startswith("[call_asknews]"):
            self.search_counts["asknews"] = self.search_counts.get("asknews", 0) + 1
        if message.startswith("[google_search"):
            self.search_counts["serper"] = self.search_counts.get("serper", 0) + 1
        if message.startswith("[google_search_agentic"):
            self.search_counts["serper_agentic"] = self.search_counts.get("serper_agentic", 0) + 1
        if message.startswith("[serper_urls]"):
            # expected format: [serper_urls] attempted=X success=Y
            parts = message.split()
            try:
                attempted = int(parts[1].split("=")[1])
                success = int(parts[2].split("=")[1])
                self.serper_urls_attempted += attempted
                self.serper_urls_success += success
            except Exception:
                pass

        if auto_level == "error":
            self.error(message)
        elif auto_level == "probability":
            self.probability(message)
        else:
            self.info(message)

    def error_lines(self) -> List[str]:
        """Return buffered messages marked as errors."""
        lines = []
        for level, msg in self.entries:
            if level == "error" or "[ERROR]" in msg:
                if msg.startswith("[ERROR]"):
                    lines.append(msg)
                else:
                    lines.append(f"[ERROR] {msg}")
        return lines

    def get_search_counts(self) -> dict:
        """Return aggregated search counts."""
        return dict(self.search_counts)

    def get_serper_url_stats(self) -> Tuple[int, int]:
        """Return cumulative serper URL attempted and success counts."""
        return self.serper_urls_attempted, self.serper_urls_success


_current_logger = RunLogger()


def get_current_logger() -> RunLogger:
    return _current_logger


def set_current_logger(logger: RunLogger) -> None:
    global _current_logger
    _current_logger = logger
