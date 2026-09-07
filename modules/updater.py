"""Small dependency-free GitHub release checker."""
import json
import re
from urllib.request import Request, urlopen

from market.version import APP_VERSION


RELEASES_URL = ('https://api.github.com/repos/Corovinus/'
                'financial_market_simulator/releases?per_page=10')


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', str(value).strip())
    return tuple(map(int, match.groups())) if match else None


def check_for_update(current=APP_VERSION, timeout=3):
    """Return the newest published release newer than *current*."""
    request = Request(RELEASES_URL, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': f'FAST/{current}',
    })
    with urlopen(request, timeout=timeout) as response:
        releases = json.load(response)
    current_key = version_key(current)
    candidates = []
    for release in releases:
        key = version_key(release.get('tag_name')) or version_key(
            release.get('name'))
        if (key and not release.get('draft') and current_key and
                key > current_key):
            candidates.append((key, release))
    if not candidates:
        return None
    _key, release = max(candidates, key=lambda item: item[0])
    return {
        'version': '.'.join(map(str, _key)),
        'url': release['html_url'],
        'prerelease': bool(release.get('prerelease')),
    }
