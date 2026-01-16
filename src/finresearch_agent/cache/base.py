from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class JSONCache(ABC):
    @abstractmethod
    def get_json(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        raise NotImplementedError
