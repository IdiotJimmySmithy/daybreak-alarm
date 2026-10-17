"""Set repository-specific metadata before publishing to GitHub."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def configure(repository, maintainer=None, root=ROOT):
    repository = repository.removeprefix('https://github.com/').removesuffix('.git').rstrip('/')
    match = re.fullmatch(r'([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]+)', repository)
    if not match or match[2] in ('.', '..'):
        raise ValueError('Use OWNER/REPOSITORY or https://github.com/OWNER/REPOSITORY')
    owner = (maintainer or match[1]).removeprefix('@')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', owner):
        raise ValueError('Maintainer must be a GitHub username')
    path = root / 'custom_components/daybreak_alarm/manifest.json'
    manifest = json.loads(path.read_text())
    manifest.update(documentation=f'https://github.com/{repository}',
                    issue_tracker=f'https://github.com/{repository}/issues', codeowners=[f'@{owner}'])
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    print(f'Configured {repository}; maintainer @{owner}. No files were uploaded.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', help='OWNER/REPOSITORY or a GitHub repository URL')
    parser.add_argument('--maintainer', help='Individual GitHub username if the repository owner is an organization')
    args = parser.parse_args()
    try:
        configure(args.repository, args.maintainer)
    except ValueError as error:
        parser.error(str(error))
