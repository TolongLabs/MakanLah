"""The deployed API installs from requirements.txt; the repo declares deps in
pyproject.toml. Two lists of the same thing drift, and the drift is invisible
until a deploy fails at import time in a place nobody is watching.

This is not hypothetical. #31 added opencc-python-reimplemented to pyproject as a
runtime dependency of `fold_variants`, which `rank.py` calls on the request path.
Had requirements.txt not been updated with it, Render would have built green and
every /recommend would have raised ModuleNotFoundError.
"""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_runtime_deps():
    data = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    return {d.strip() for d in data['project']['dependencies']}


def _requirements():
    lines = (ROOT / 'requirements.txt').read_text().splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith('#')}


class TestDeployManifest:
    def test_requirements_matches_pyproject_exactly(self):
        pyproject, reqs = _pyproject_runtime_deps(), _requirements()
        missing, extra = pyproject - reqs, reqs - pyproject
        assert not missing, f'requirements.txt is missing {sorted(missing)} -- the deployed API would fail at import'
        assert not extra, f'requirements.txt carries {sorted(extra)} that pyproject.toml does not declare'

    def test_dev_only_deps_are_not_shipped(self):
        # The deployed API must not carry a test client.
        assert not {r for r in _requirements() if re.match(r'^(pytest|httpx|ruff)\b', r)}


class TestRenderBlueprint:
    """render.yaml is committed, so it must never be able to carry a credential."""

    @pytest.fixture
    def service(self):
        # Imported, never skipped. pyyaml is a dev dependency for exactly this
        # reason: a skipped blueprint check and a passing one look identical in a
        # CI log, and this file is the only thing standing between a committed
        # yaml and a credential in it.
        import yaml

        return yaml.safe_load((ROOT / 'render.yaml').read_text())['services'][0]

    def test_region_is_singapore(self, service):
        # KL users, a Singapore Neon, a Singapore DashScope. A US free tier adds
        # ~200ms each way to a p95 that only just meets its target.
        assert service['region'] == 'singapore'

    def test_secrets_are_prompted_never_valued(self, service):
        for env in service['envVars']:
            if env.get('sync') is False:
                assert 'value' not in env, f'{env["key"]} carries a value in a committed file'

    def test_database_url_is_a_prompted_secret(self, service):
        prompted = {e['key'] for e in service['envVars'] if e.get('sync') is False}
        assert {'DATABASE_URL', 'DASHSCOPE_API_KEY'} <= prompted

    def test_start_command_binds_the_port_render_provides(self, service):
        # Binding 127.0.0.1 or a fixed port makes the service unreachable and the
        # health check fails with no useful error.
        assert '0.0.0.0' in service['startCommand'] and '$PORT' in service['startCommand']

    def test_build_does_not_use_pip_install_dot(self, service):
        # pyproject.toml declares no build backend, so `pip install .` fails.
        assert 'pip install .' not in service['buildCommand']
        assert 'requirements.txt' in service['buildCommand']


class TestVercelConfig:
    """vercel.json is what actually ships the API. Every assertion here is a
    failure that would deploy green and be wrong in production."""

    @pytest.fixture
    def cfg(self):
        import json

        return json.loads((ROOT / 'vercel.json').read_text())

    def test_region_is_singapore(self, cfg):
        # Vercel defaults new projects to iad1, Washington DC. Neon is in
        # ap-southeast-1 and the model API is in Singapore, so iad1 adds a
        # transpacific round trip to every query and nothing would fail loudly.
        assert cfg['regions'] == ['sin1']

    def test_exactly_one_function_is_built(self, cfg):
        # Vercel builds every file under api/ as its own function. Without an
        # explicit builds block, api/main.py ships a second time at /api/main:
        # one app, two cold starts, two public paths.
        assert len(cfg['builds']) == 1
        assert cfg['builds'][0]['src'] == 'api/index.py'

    def test_the_package_travels_with_the_function(self, cfg):
        # api/main.py imports makanlah, which sits beside api/ rather than inside
        # it, so it is not picked up by the builder's own tracing.
        included = cfg['builds'][0]['config']['includeFiles']
        assert any(i.startswith('makanlah') for i in included), included

    def test_every_route_reaches_the_app(self, cfg):
        routes = cfg['routes']
        assert any(r['src'] == '/(.*)' and r['dest'] == 'api/index.py' for r in routes), routes

    def test_duration_outlives_a_slow_query(self, cfg):
        # p95 is ~2.9s and the embed and re-rank deadlines bound the tail, but a
        # cold start plus both model calls must still fit.
        assert cfg['builds'][0]['config']['maxDuration'] >= 30

    def test_entrypoint_exports_an_asgi_app(self):
        src = (ROOT / 'api' / 'index.py').read_text()
        assert 'from api.main import app' in src


class TestHealthNamesItsBuild:
    """ "Is the fix deployed?" must be answerable from outside the process.

    Two sessions disagreed for seven minutes about whether a ranking change was
    live, with no way to tell whether they were hitting the same build. The
    client has carried build.json since it was first deployed; the API reported
    corpus counts and four self-reported booleans and nothing about itself.

    This is the same shape as /health reporting `database: true` from a bundled
    dotenv: a status surface that cannot distinguish two states it is asked to
    distinguish.
    """

    def test_health_exposes_a_commit_field(self):
        src = (ROOT / 'api' / 'main.py').read_text()
        assert "'commit': commit" in src, 'health must name the commit it is running'

    def test_the_commit_is_read_from_the_environment_not_invented(self):
        src = (ROOT / 'api' / 'main.py').read_text()
        assert 'VERCEL_GIT_COMMIT_SHA' in src
        # Absent the variable it must report None rather than a placeholder: an
        # unknown build is a fact, and a fabricated one is worse than silence.
        assert "or os.environ.get('GIT_COMMIT_SHA')" in src
