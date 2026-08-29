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
