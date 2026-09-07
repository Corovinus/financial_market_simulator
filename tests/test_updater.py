import io
import json
import unittest
from unittest.mock import patch

from modules.updater import check_for_update, version_key


class UpdateTests(unittest.TestCase):
    def test_semantic_version_parser(self):
        self.assertEqual(version_key('v1.2.3'), (1, 2, 3))
        self.assertEqual(version_key('0.2.0'), (0, 2, 0))
        self.assertIsNone(version_key('Beta'))

    def test_newest_published_release_is_selected(self):
        releases = [
            {'tag_name': 'v0.2.0', 'name': 'Current', 'draft': False,
             'prerelease': True, 'html_url': 'https://example/current'},
            {'tag_name': 'v0.3.0', 'name': 'Next', 'draft': False,
             'prerelease': True, 'html_url': 'https://example/next'},
            {'tag_name': 'v9.0.0', 'name': 'Draft', 'draft': True,
             'prerelease': False, 'html_url': 'https://example/draft'},
        ]
        response = io.BytesIO(json.dumps(releases).encode('utf-8'))
        with patch('modules.updater.urlopen', return_value=response):
            update = check_for_update('0.2.0')
        self.assertEqual(update, {
            'version': '0.3.0', 'url': 'https://example/next',
            'prerelease': True})


if __name__ == '__main__':
    unittest.main()
