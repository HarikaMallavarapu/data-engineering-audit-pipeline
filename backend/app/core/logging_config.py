import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime

from app.core.config import Settings

request_id_context_var: ContextVar[str | None] = ContextVar("datatrace_request_id", default=None)


@contextmanager
def bind_request_id(request_id: str) -> Iterator[None]:
    token = request_id_context_var.set(request_id)
    try:
        yield
    finally:
        request_id_context_var.reset(token)


class CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", None) or request_id_context_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "run_id", "attempt_id"):
            if value := getattr(record, key, None):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
