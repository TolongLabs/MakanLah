"""Configuration, loaded from the environment.

Nothing here prints a value. `describe()` names keys and whether they are set,
which is what a health check and a preflight need.
"""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Populate os.environ from .env without overriding a real environment variable.

    Deployed processes get real environment variables; only the workstation has a
    .env file. Not overriding means a deploy cannot be surprised by a stale local file.
    """
    p = path or ROOT / '.env'
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        v = v.strip().strip('"').strip("'")
        if v.startswith('<'):  # an unconfirmed placeholder is not a value
            continue
        os.environ.setdefault(k.strip(), v)


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    database_url_direct: str | None
    extract_base_url: str
    extract_api_key: str | None
    extract_model: str
    embed_base_url: str
    embed_api_key: str | None
    embed_model: str
    embed_dim: int
    rerank_base_url: str | None
    rerank_api_key: str | None
    rerank_model: str
    nominatim_base_url: str
    nominatim_user_agent: str
    cors_origins: tuple[str, ...]


def settings() -> Settings:
    load_dotenv()
    e = os.environ.get

    # DashScope is the extraction lane; OpenRouter is the fallback so a missing
    # DashScope quota degrades rather than stops. Both are OpenAI-compatible, so
    # only the base URL, key and model differ.
    if e('DASHSCOPE_API_KEY'):
        x_base = e('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
        x_key, x_model = e('DASHSCOPE_API_KEY'), e('DASHSCOPE_MODEL_EXTRACT', 'qwen-plus')
    else:
        x_base, x_key = 'https://openrouter.ai/api/v1', e('OPENROUTER_API_KEY')
        x_model = e('OPENROUTER_MODEL_EXTRACT', 'qwen/qwen3-235b-a22b-2507')

    return Settings(
        database_url=e('DATABASE_URL'),
        database_url_direct=e('DATABASE_URL_UNPOOLED'),
        extract_base_url=x_base,
        extract_api_key=x_key,
        extract_model=x_model,
        embed_base_url=e('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'),
        embed_api_key=e('DASHSCOPE_API_KEY'),
        embed_model=e('DASHSCOPE_MODEL_EMBED', 'text-embedding-v3'),
        embed_dim=int(e('EMBEDDING_DIM', '1024')),
        # The re-rank is the interactive lane: a user is waiting, and it is 96%
        # of request latency. Measured on this corpus, 20 candidates each:
        #   qwen-turbo (DashScope, Singapore)  1.38s   most results
        #   qwen-flash (DashScope)             1.13s   fewer results
        #   qwen3-30b (OpenRouter)             1.13s
        #   qwen-plus  (DashScope)             2.33s
        #   qwen3-235b (OpenRouter)            8.97s   the previous default
        # qwen-turbo wins on results-per-second, and DashScope is nearer KL.
        rerank_base_url=(
            e('HERMES_COPILOT_BASE_URL')
            or (e('DASHSCOPE_BASE_URL') if e('DASHSCOPE_API_KEY') else None)
            or 'https://openrouter.ai/api/v1'
        ),
        rerank_api_key=e('HERMES_API_KEY') or e('DASHSCOPE_API_KEY') or e('OPENROUTER_API_KEY'),
        rerank_model=e('RERANK_MODEL')
        or ('qwen-turbo' if e('DASHSCOPE_API_KEY') else 'qwen/qwen3-30b-a3b-instruct-2507'),
        nominatim_base_url=e('NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org'),
        nominatim_user_agent=e('NOMINATIM_USER_AGENT', 'MakanLah/0.1'),
        cors_origins=tuple(x for x in (e('CORS_ORIGINS', '') or '').split(',') if x) or ('*',),
    )


def describe() -> dict[str, bool]:
    """Key presence, never a value. Safe to log and to return from /health."""
    s = settings()
    return {
        'database': bool(s.database_url),
        'extract': bool(s.extract_api_key),
        'embed': bool(s.embed_api_key),
        'rerank': bool(s.rerank_api_key),
    }
