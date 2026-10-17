"""Validate HACS structure, assets, versions, and configured repository identity."""
import argparse
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT, allow_template=False):
    component = root/'custom_components/daybreak_alarm'
    integrations = [p.name for p in (root/'custom_components').iterdir() if p.is_dir() and p.name != '__pycache__']
    assert integrations == ['daybreak_alarm'], 'Exactly one integration is required'
    manifest = json.loads((component/'manifest.json').read_text())
    hacs = json.loads((root/'hacs.json').read_text())
    for key in ('domain', 'name', 'version', 'documentation', 'issue_tracker', 'codeowners'):
        assert manifest.get(key), f'Missing manifest value: {key}'
    assert manifest['domain'] == 'daybreak_alarm'
    assert re.fullmatch(r'\d+\.\d+\.\d+', manifest['version'])
    assert hacs['name'] == manifest['name']
    assert hacs.get('content_in_root', False) is False
    assert not hacs.get('zip_release', False), 'This repository uses normal source downloads'
    assert manifest['issue_tracker'] == manifest['documentation'].rstrip('/')+'/issues'
    assert manifest['documentation'].startswith('https://github.com/')
    if not allow_template:
        assert 'YOUR_GITHUB_USERNAME' not in json.dumps(manifest), 'Run python tools/configure_repository.py OWNER/REPOSITORY before publishing'
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse((component/'const.py').read_text()).body if isinstance(n, ast.Assign)}
    assert constants['VERSION'] == manifest['version'] == json.loads((root/'package.json').read_text())['version']
    for name in ('__init__.py', 'config_flow.py', 'entity.py', 'switch.py', 'button.py', 'sensor.py', 'frontend/panel.js', 'frontend/card.js', 'frontend/sounds/daybreak.wav', 'frontend/sounds/soft.wav', 'frontend/sounds/pulse.wav', 'translations/en.json'):
        assert (component/name).is_file(), f'Missing runtime file: {name}'
    assert f'export const FRONTEND_VERSION = "{manifest["version"]}"' in (component/'frontend/panel.js').read_text()
    assert f'./panel.js?v={manifest["version"]}' in (component/'frontend/card.js').read_text()
    assert (root/'README.md').is_file()
    print('Repository validation passed' + (' (template identity allowed; configure before publishing)' if allow_template else ''))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-template', action='store_true')
    args = parser.parse_args()
    validate(allow_template=args.allow_template)
