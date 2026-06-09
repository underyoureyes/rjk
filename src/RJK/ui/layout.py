from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def get_index_html() -> str:
    """Read and return the single-page application HTML."""
    return (_PROJECT_ROOT / "templates" / "index.html").read_text(encoding="utf-8")


BRAND_BLUE = "#003087"
BRAND_LIGHT = "#f0f4ff"
