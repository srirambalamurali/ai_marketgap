from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime
from typing import Any

import chromadb
import requests
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger("services.chromadb")


def _sanitize_scalar(value: Any) -> str | int | float | bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        sanitized = [_sanitize_scalar(item) for item in value]
        return json.dumps([item for item in sanitized if item is not None], default=str)
    if isinstance(value, dict):
        return json.dumps(_sanitize_metadata(value), default=str, ensure_ascii=False)
    return str(value)


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, str | int | float | bool]:
    sanitized: dict[str, str | int | float | bool] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if key == "level":
            try:
                sanitized[key] = int(value)
            except Exception:
                continue
            continue
        scalar = _sanitize_scalar(value)
        if scalar is None:
            continue
        sanitized[key] = scalar
    return sanitized


def _sanitize_where(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if item is None:
                continue
            if key == "level":
                try:
                    sanitized[key] = int(item)
                except Exception:
                    continue
                continue
            if key.startswith("$"):
                sanitized[key] = _sanitize_where(item)
                continue
            sanitized[key] = _sanitize_where(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_where(item) for item in value if item is not None]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


class ChromaDBService:
    _instance: ChromaDBService | None = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> ChromaDBService:
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False  # type: ignore[attr-defined]
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._client: chromadb.ClientAPI | None = None
        self._client_lock = threading.RLock()
        self._connected = False
        self._last_error: str | None = None
        self._last_heartbeat_ms: float | None = None
        self._operation_timeout_seconds = max(60, int(self.settings.request_timeout_seconds))
        self._heartbeat_timeout_seconds = min(20, int(self.settings.request_timeout_seconds))

    @property
    def settings(self):
        return get_settings()

    @property
    def collection_name(self) -> str:
        return self.settings.chroma_collection

    async def connect(self) -> bool:
        if self._client is not None and self._connected:
            return True
        try:
            await asyncio.wait_for(asyncio.to_thread(self._connect_sync), timeout=self._operation_timeout_seconds)
            return True
        except Exception as exc:
            self._connected = False
            self._last_error = str(exc)
            logger.warning("Chroma connect failed: %s", exc)
            return False

    def _connect_sync(self) -> None:
        with self._client_lock:
            self._client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._connected = True
            self._last_error = None

    async def heartbeat(self) -> dict[str, Any]:
        url = f"http://{self.settings.chroma_host}:{self.settings.chroma_port}/api/v2/heartbeat"
        start = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(requests.get, url, timeout=self._heartbeat_timeout_seconds),
                timeout=self._operation_timeout_seconds,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            self._last_heartbeat_ms = elapsed_ms
            ok = response.ok
            if ok:
                self._connected = True
                self._last_error = None
            else:
                self._connected = False
                self._last_error = f"Heartbeat returned HTTP {response.status_code}"
            return {
                "connected": ok,
                "status_code": response.status_code,
                "latency_ms": elapsed_ms,
                "error": None if ok else self._last_error,
            }
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            self._connected = False
            self._last_error = str(exc)
            self._last_heartbeat_ms = elapsed_ms
            return {
                "connected": False,
                "status_code": None,
                "latency_ms": elapsed_ms,
                "error": str(exc),
            }

    async def create_collection(self, name: str | None = None):
        collection_name = name or self.collection_name
        client = await self._ensure_client()
        return await asyncio.wait_for(
            asyncio.to_thread(
                client.get_or_create_collection,
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            ),
            timeout=self._operation_timeout_seconds,
        )

    async def get_collection(self, name: str | None = None):
        return await self.create_collection(name)

    async def collection_exists(self, name: str | None = None) -> bool:
        collection_name = name or self.collection_name
        try:
            client = await self._ensure_client()
        except Exception:
            return False

        def _list_names() -> list[str]:
            items = client.list_collections()
            names: list[str] = []
            for item in items:
                if isinstance(item, str):
                    names.append(item)
                elif hasattr(item, "name"):
                    names.append(str(getattr(item, "name")))
                elif isinstance(item, dict) and "name" in item:
                    names.append(str(item["name"]))
            return names

        try:
            names = await asyncio.wait_for(
                asyncio.to_thread(_list_names),
                timeout=self._operation_timeout_seconds,
            )
            return collection_name in names
        except Exception as exc:
            logger.warning("Failed to list Chroma collections: %s", exc)
            return False

    async def upsert_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
        collection_name: str | None = None,
    ) -> int:
        if not ids:
            return 0
        sanitized_metadatas = [_sanitize_metadata(metadata) for metadata in metadatas]
        await self._execute_with_retry(
            "upsert",
            collection_name=collection_name,
            ids=ids,
            documents=documents,
            metadatas=sanitized_metadatas,
            embeddings=embeddings,
        )
        return len(ids)

    async def query_documents(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict | None = None,
        collection_name: str | None = None,
    ) -> dict:
        return await self._execute_with_retry(
            "query",
            collection_name=collection_name,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=_sanitize_where(where) if where is not None else None,
        )

    async def delete_documents(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
        collection_name: str | None = None,
    ) -> int:
        await self._execute_with_retry(
            "delete",
            collection_name=collection_name,
            ids=ids,
            where=_sanitize_where(where) if where is not None else None,
        )
        return len(ids or [])

    async def count_documents(self, collection_name: str | None = None) -> int:
        collection = await self.get_collection(collection_name)

        def _count() -> int:
            return int(collection.count())

        return await asyncio.wait_for(
            asyncio.to_thread(_count),
            timeout=self._operation_timeout_seconds,
        )

    async def health(self, collection_name: str | None = None) -> dict[str, Any]:
        heartbeat = await self.heartbeat()
        connected = bool(heartbeat["connected"])
        collection_exists = False
        embedded_documents = 0

        if connected:
            try:
                collection = await self.get_collection(collection_name)
                collection_exists = collection is not None
                embedded_documents = await self.count_documents(collection_name)
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Chroma health check failed: %s", exc)

        status = "healthy" if connected and collection_exists else "degraded"
        return {
            "chromadb_connected": connected,
            "collection_exists": collection_exists,
            "embedded_documents": embedded_documents,
            "status": status,
            "latency_ms": heartbeat["latency_ms"],
            "error": heartbeat["error"] if not connected else None,
            "collection_name": collection_name or self.collection_name,
            "last_error": self._last_error,
        }

    async def _ensure_client(self) -> chromadb.ClientAPI:
        if self._client is None or not self._connected:
            if not await self.connect():
                raise RuntimeError(
                    f"ChromaDB unavailable at {self.settings.chroma_host}:{self.settings.chroma_port}"
                )
        assert self._client is not None
        return self._client

    async def _execute_with_retry(self, operation: str, collection_name: str | None = None, **kwargs):
        await self._ensure_client()
        collection = await self.get_collection(collection_name)
        method = getattr(collection, operation)
        try:
            if "where" in kwargs and kwargs["where"] is not None:
                kwargs["where"] = _sanitize_where(kwargs["where"])
            return await asyncio.wait_for(
                asyncio.to_thread(method, **kwargs),
                timeout=self._operation_timeout_seconds,
            )
        except Exception as exc:
            logger.warning("Chroma operation failed, reconnecting once: %s", exc)
            with self._client_lock:
                self._client = None
                self._connected = False
            await self._ensure_client()
            collection = await self.get_collection(collection_name)
            method = getattr(collection, operation)
            return await asyncio.wait_for(
                asyncio.to_thread(method, **kwargs),
                timeout=self._operation_timeout_seconds,
            )


_chroma_service: ChromaDBService | None = None


def get_chroma_service() -> ChromaDBService:
    global _chroma_service
    if _chroma_service is None:
        _chroma_service = ChromaDBService()
    return _chroma_service
