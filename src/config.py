"""Paths, env loading and config loaders for companies.yaml and metrics.yaml."""
from pathlib import Path

import dotenv
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
RAW_HTML_DIR = DATA_DIR / "raw_html"
XBRL_DIR = DATA_DIR / "xbrl"
PARSED_DIR = DATA_DIR / "parsed"
FACTS_DIR = DATA_DIR / "facts"
LLM_CACHE_DIR = DATA_DIR / "llm_cache"
ENTITIES_DIR = DATA_DIR / "entities"
GRAPH_DIR = ROOT / "graph"
BENCHMARK_DIR = ROOT / "benchmark"
REPORT_DIR = ROOT / "report"  # metrics.json and per_question.csv; the PDF lives in results/


def load_env() -> None:
    """Load .env from the repo root. Existing environment variables win."""
    dotenv.load_dotenv(ROOT / ".env")


def load_companies() -> list[dict]:
    with open(CONFIG_DIR / "companies.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)["companies"]


def load_metrics() -> dict:
    """Return {"metrics": [...], "derived": [...]} from metrics.yaml."""
    with open(CONFIG_DIR / "metrics.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
