"""Check the publishing step on a temporary copy, never a real GitHub repo."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from support import ROOT


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositoryTests(unittest.TestCase):
    def test_configuring_repository_produces_valid_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT/'custom_components', root/'custom_components')
            for name in ('hacs.json', 'package.json', 'README.md'):
                shutil.copy(ROOT/name, root/name)
            load('configure_repository').configure('https://github.com/example-user/daybreak-alarm', root=root)
            load('validate_repository').validate(root=root)
            manifest = json.loads((root/'custom_components/daybreak_alarm/manifest.json').read_text())
            self.assertEqual(manifest['codeowners'], ['@example-user'])
            self.assertEqual(manifest['issue_tracker'], 'https://github.com/example-user/daybreak-alarm/issues')

    def test_template_identity_cannot_pass_publish_validation(self):
        manifest = json.loads((ROOT/'custom_components/daybreak_alarm/manifest.json').read_text())
        if 'YOUR_GITHUB_USERNAME' not in json.dumps(manifest):
            self.skipTest('Repository identity is already configured')
        with self.assertRaisesRegex(AssertionError, 'configure_repository'):
            load('validate_repository').validate()

    def test_bad_repository_url_is_rejected(self):
        with self.assertRaises(ValueError):
            load('configure_repository').configure('https://example.com/not-github/repo')
