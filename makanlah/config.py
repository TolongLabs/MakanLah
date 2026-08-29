"""Configuration, loaded from the environment.

Nothing here prints a value. `describe()` names keys and whether they are set,
which is what a health check and a preflight need.
"""

import os
import re
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
    embed_timeout: float
    rerank_base_url: str | None
    rerank_api_key: str | None
    rerank_model: str
    rerank_thinking: bool
    rerank_timeout: float
    copilot_base_url: str | None
    copilot_api_key: str | None
    copilot_model: str
    copilot_thinking: bool
    companion_base_url: str
    companion_api_key: str | None
    companion_model: str
    companion_timeout: float
    nominatim_base_url: str
    nominatim_user_agent: str
    cors_origins: tuple[str, ...]
    cors_origin_regex: str


def settings() -> Settings:
    load_dotenv()
    e = os.environ.get

    # DashScope is the extraction lane; OpenRouter is the fallback so a missing
    # DashScope quota degrades rather than stops. Both are OpenAI-compatible, so
    # only the base URL, key and model differ.
    # Model pinning, measured against the ModelStudio free-quota console 2026-08-28.
    # The ROLLING aliases carry no free quota -- qwen-plus, qwen-turbo and qwen-flash
    # are all "No Free Quota / Not Supported". The DATED snapshots do, 1M tokens each
    # expiring 2026-10-13, so every lane below is pinned to a date rather than a name
    # that silently moves onto a paid tier. Re-check the console before repinning.
    if e('DASHSCOPE_API_KEY'):
        x_base = e('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
        x_key, x_model = e('DASHSCOPE_API_KEY'), e('DASHSCOPE_MODEL_EXTRACT', 'qwen-plus-2025-07-28')
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
        # Batch lane: nobody is waiting, but 120s per call let a hung provider stall
        # ingestion for minutes (issue #41). The deadline is shared across batches.
        embed_timeout=float(e('EMBED_TIMEOUT', '10.0')),
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
        or ('qwen3.7-flash-2026-07-15' if e('DASHSCOPE_API_KEY') else 'qwen/qwen3-30b-a3b-instruct-2507'),
        # qwen3.x thinks by default, and thinking costs 9x here: the flash lane ran
        # 4.06/15.48/20.75s with it on and 1.04/2.02/2.26s with it off, same prompts.
        # A user is waiting on this lane, so it is off unless explicitly re-enabled.
        rerank_thinking=e('RERANK_THINKING', '').lower() in ('1', 'true', 'yes'),
        # The interactive budget, not a generous ceiling. Re-rank is 94% of p95
        # and its tail is upstream variance: measured p95 1.64s in one window and
        # 8.87s in another, same prompts, same lane. A 60s timeout let a single
        # slow call blow a 3s target by 4x. Past this the retrieval order ships
        # instead -- worse ranking, still cited, still fast.
        rerank_timeout=float(e('RERANK_TIMEOUT', '4.0')),
        # The copilot is its own lane, not a reuse of the re-rank one. Re-rank is
        # tuned for "pick 10 and write 12 words"; the copilot answers a question
        # from evidence, where getting a citation wrong is worse than getting an
        # ordering wrong. Same free-quota snapshot, separately overridable.
        copilot_base_url=(
            e('HERMES_COPILOT_BASE_URL')
            or (
                e('DASHSCOPE_BASE_URL', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
                if e('DASHSCOPE_API_KEY')
                else None
            )
            or 'https://openrouter.ai/api/v1'
        ),
        copilot_api_key=e('HERMES_API_KEY') or e('DASHSCOPE_API_KEY') or e('OPENROUTER_API_KEY'),
        copilot_model=e('COPILOT_MODEL')
        or ('qwen3.7-flash-2026-07-15' if e('DASHSCOPE_API_KEY') else 'qwen/qwen3-30b-a3b-instruct-2507'),
        copilot_thinking=e('COPILOT_THINKING', '').lower() in ('1', 'true', 'yes'),
        # The companion is its own lane and shares nothing with the two above. It
        # writes one cheerful sentence for the onboarding wizard, sees no corpus
        # row and makes no claim, so it is pointed at whatever free quota is
        # spare rather than at the lane a citation depends on. Gemini's
        # OpenAI-compatible path, so models._post works unchanged.
        companion_base_url=e('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai'),
        companion_api_key=e('GEMINI_API_KEY'),
        companion_model=e('GEMINI_MODEL_L2D', 'gemini-3.5-flash-lite'),
        # Somebody is mid-wizard and reading a question. Past this the scripted
        # line is spoken instead, which is a fine outcome and not an error.
        companion_timeout=float(e('COMPANION_TIMEOUT', '3.0')),
        nominatim_base_url=e('NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org'),
        nominatim_user_agent=e('NOMINATIM_USER_AGENT', 'MakanLah/0.1'),
        cors_origins=tuple(x for x in (e('CORS_ORIGINS', '') or '').split(',') if x),
        cors_origin_regex=e('CORS_ORIGIN_REGEX') or _default_cors_regex(e('CF_PAGES_PROJECT', 'makanlah-b5h')),
    )


def _default_cors_regex(project: str) -> str:
    """Who may call this API from a browser, when CORS_ORIGINS is not set.

    `*` was right for a local API and is wrong for a public one -- not because it
    leaks a session (auth is a Bearer header, not a cookie, so allow_credentials
    is off and no site can ride a signed-in user) but because every request
    spends a model call. An open CORS policy invites someone else's page to spend
    our budget.

    A fixed list would break Cloudflare Pages previews, which get their own
    subdomain per branch, so this matches the project's own hosts and localhost
    on any port. Set CORS_ORIGINS to override with an explicit list.
    """
    host = re.escape(project)
    return rf'^https://([a-z0-9-]+\.)?{host}\.pages\.dev$|^http://(localhost|127\.0\.0\.1)(:\d+)?$'


def describe() -> dict[str, bool]:
    """Key presence, never a value. Safe to log and to return from /health."""
    s = settings()
    return {
        'database': bool(s.database_url),
        'extract': bool(s.extract_api_key),
        'embed': bool(s.embed_api_key),
        'rerank': bool(s.rerank_api_key),
    }
