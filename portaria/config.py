import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _parse_source(raw: str) -> int | str:
    val = (raw or "0").strip()
    if val.isdigit():
        return int(val)
    return val


@dataclass
class PortariaConfig:
    api_url: str
    device_key: str
    source: int | str
    portal: str
    modo: str
    width: int
    height: int
    detect_width: int
    confirm_frames: int
    cooldown_seconds: int
    unknown_seconds: float
    cosine_threshold: float
    margin_threshold: float
    headless: bool
    models_dir: Path
    spool_db_path: Path


def load_config(
    source_override=None,
    portal_override: str | None = None,
    modo_override: str | None = None,
    headless_override: bool | None = None,
) -> PortariaConfig:
    modo = (modo_override or os.getenv("PORTARIA_MODO", "auto")).strip().lower()
    if modo not in {"auto", "entrada", "saida"}:
        modo = "auto"

    return PortariaConfig(
        api_url=os.getenv("PORTARIA_API_URL", "http://localhost:8000/api").rstrip("/"),
        device_key=os.getenv("PORTARIA_DEVICE_KEY", "").strip(),
        source=_parse_source(str(source_override)) if source_override is not None else _parse_source(os.getenv("PORTARIA_SOURCE", "0")),
        portal=(portal_override or os.getenv("PORTARIA_PORTAL", "Portaria principal")).strip(),
        modo=modo,
        width=max(320, int(os.getenv("PORTARIA_WIDTH", "960"))),
        height=max(240, int(os.getenv("PORTARIA_HEIGHT", "540"))),
        detect_width=max(240, int(os.getenv("PORTARIA_DETECT_WIDTH", "480"))),
        confirm_frames=max(1, int(os.getenv("PORTARIA_CONFIRM_FRAMES", "2"))),
        cooldown_seconds=max(5, int(os.getenv("PORTARIA_COOLDOWN", "45"))),
        unknown_seconds=max(1.0, float(os.getenv("PORTARIA_UNKNOWN_SECONDS", "2.5"))),
        cosine_threshold=float(os.getenv("PORTARIA_THRESHOLD", "0.380")),
        margin_threshold=float(os.getenv("PORTARIA_MARGIN", "0.04")),
        headless=headless_override if headless_override is not None else (os.getenv("PORTARIA_HEADLESS", "0") == "1"),
        models_dir=BASE_DIR / "models",
        spool_db_path=BASE_DIR / "spool.db",
    )
