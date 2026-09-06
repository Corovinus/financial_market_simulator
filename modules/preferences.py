"""Persistent user-interface preferences shared by all screens."""
import json
import os
from pathlib import Path
import sys


DEFAULTS = {
    'scale': 1.25,
    'font_scale': 1.0,
    'theme': 'dark',
    'sound': True,
    'fullscreen': False,
    'window_size': [1200, 750],
}

_values = None
_path = None


def preferences_path():
    root = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parents[1])
    return root / 'settings.json'


def _fallback_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'FAST' / 'settings.json'


def normalize_preferences(values):
    result = dict(DEFAULTS)
    if not isinstance(values, dict):
        return result
    scale = values.get('scale')
    if type(scale) in (int, float) and 0.5 <= scale <= 5:
        result['scale'] = float(scale)
    font_scale = values.get('font_scale')
    if type(font_scale) in (int, float) and 0.8 <= font_scale <= 1.2:
        result['font_scale'] = round(float(font_scale), 1)
    if values.get('theme') in ('dark', 'light'):
        result['theme'] = values['theme']
    for key in ('sound', 'fullscreen'):
        if type(values.get(key)) is bool:
            result[key] = values[key]
    size = values.get('window_size')
    if (isinstance(size, (list, tuple)) and len(size) == 2 and
            all(type(value) is int and 100 <= value <= 10000 for value in size)):
        result['window_size'] = list(size)
    return result


def get_preferences():
    global _values, _path
    if _values is None:
        primary = preferences_path()
        for candidate in (primary, _fallback_path()):
            try:
                _values = normalize_preferences(json.loads(
                    candidate.read_text(encoding='utf-8')))
                _path = candidate
                break
            except OSError:
                continue
            except (ValueError, TypeError, json.JSONDecodeError):
                _values, _path = dict(DEFAULTS), candidate
                break
        else:
            _values, _path = dict(DEFAULTS), primary
    return _values


def set_preferences(**changes):
    global _values, _path
    current = get_preferences()
    candidate = normalize_preferences({**current, **changes})
    _values.clear()
    _values.update(candidate)
    target = _path or preferences_path()
    try:
        target.write_text(json.dumps(_values, ensure_ascii=False, indent=2),
                          encoding='utf-8')
    except OSError:
        target = _fallback_path()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(_values, ensure_ascii=False, indent=2),
                              encoding='utf-8')
            _path = target
        except OSError:
            pass
    return _values
