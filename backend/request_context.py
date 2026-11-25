"""Keep demo uploads separate for each browser session."""

from contextvars import ContextVar
from pathlib import Path


session_id: ContextVar[str | None] = ContextVar("finshyt_session_id", default=None)
DATA_DIR = Path(__file__).resolve().parent.parent / "data2"


def session_file(filename: str) -> Path | None:
    current = session_id.get()
    if not current:
        return None
    return DATA_DIR / "sessions" / current / filename
