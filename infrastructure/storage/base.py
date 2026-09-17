"""Document storage interface with S3 semantics (Blueprint §20 Storage).

Local implementation: filesystem (LocalDocumentStore).
AWS implementation (post-account): S3DocumentStore with the same method
surface — application code must not depend on the backend.
"""
from __future__ import annotations

from typing import Protocol


class DocumentStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def list(self, prefix: str) -> list[str]: ...
