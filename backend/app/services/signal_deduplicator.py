import hashlib
from app.schemas.signals import Signal
from app.utils.logging import get_logger

logger = get_logger("services.deduplicator")

SIMILARITY_THRESHOLD = 0.85


class SignalDeduplicator:
    def __init__(self, similarity_threshold: float = SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold
        self._seen_hashes: set[str] = set()
        self._seen_titles: list[str] = []

    def _content_hash(self, signal: Signal) -> str:
        raw = f"{signal.source}:{signal.source_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _title_hash(self, title: str) -> str:
        normalized = title.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _is_title_similar(self, new_title: str) -> bool:
        new_words = set(new_title.lower().strip().split())
        if not new_words:
            return False
        for existing in self._seen_titles:
            existing_words = set(existing.split())
            if not existing_words:
                continue
            smaller, larger = (
                (new_words, existing_words)
                if len(new_words) <= len(existing_words)
                else (existing_words, new_words)
            )
            if smaller.issubset(larger) and len(smaller) / len(larger) >= 0.6:
                return True
        return False

    def _is_content_similar(self, signal: Signal, existing: list[Signal]) -> bool:
        for ex in existing:
            if ex.source == signal.source and ex.source_id == signal.source_id:
                return True
        return False

    def deduplicate(self, signals: list[Signal], existing: list[Signal] | None = None) -> list[Signal]:
        existing = existing or []
        unique: list[Signal] = []
        stats = {"total": len(signals), "hash_dupes": 0, "title_dupes": 0, "kept": 0}

        for signal in signals:
            if signal.source_id and self._is_content_similar(signal, existing):
                stats["hash_dupes"] += 1
                continue

            if signal.source_id:
                content_hash = self._content_hash(signal)
                if content_hash in self._seen_hashes:
                    stats["hash_dupes"] += 1
                    continue

            if self._is_title_similar(signal.title):
                stats["title_dupes"] += 1
                continue

            if signal.source_id:
                self._seen_hashes.add(self._content_hash(signal))
            self._seen_titles.append(signal.title.lower().strip())
            unique.append(signal)
            stats["kept"] += 1

        logger.info(
            "Dedup: %d total, %d hash_dupes, %d title_dupes, %d kept",
            stats["total"], stats["hash_dupes"], stats["title_dupes"], stats["kept"],
        )
        return unique

    def reset(self) -> None:
        self._seen_hashes.clear()
        self._seen_titles.clear()
