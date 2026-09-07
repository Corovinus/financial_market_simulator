"""Shared DOS text rendering helpers and logical-resolution scaling."""
from __future__ import annotations

import time


_held_arrows = {}
_REPEAT_DELAY = 0.35
_REPEAT_INTERVAL = 0.065


def open_scaled_display(pygame, size, scale, caption):
    """Return a fixed-size pixel canvas and a resizable scaled window."""
    if not isinstance(scale, (int, float)) or not 0.5 <= float(scale) <= 5:
        raise ValueError("Масштаб должен быть числом от 0.5 до 5")
    base_size = (int(size[0]), int(size[1]))
    from .preferences import get_preferences
    from .theme import apply_theme
    preferences = get_preferences()
    apply_theme(preferences['theme'])
    window_size = tuple(preferences.get('window_size') or
                        [max(1, round(value * float(scale))) for value in base_size])
    flags = pygame.FULLSCREEN if preferences['fullscreen'] else pygame.RESIZABLE
    window = pygame.display.set_mode((0, 0) if preferences['fullscreen'] else window_size,
                                     flags)
    pygame.display.set_caption(caption)
    pygame.key.set_repeat()
    _held_arrows.clear()
    return pygame.Surface(base_size), window


def resize_window(pygame, canvas, scale):
    from .preferences import set_preferences
    scale = max(0.5, min(5.0, round(float(scale), 2)))
    size = (round(canvas.get_width() * scale),
            round(canvas.get_height() * scale))
    set_preferences(scale=scale, window_size=list(size), fullscreen=False)
    return pygame.display.set_mode(size, pygame.RESIZABLE)


def toggle_fullscreen(pygame):
    from .preferences import get_preferences, set_preferences
    preferences = get_preferences()
    fullscreen = not preferences['fullscreen']
    set_preferences(fullscreen=fullscreen)
    flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
    size = (0, 0) if fullscreen else tuple(preferences['window_size'])
    return pygame.display.set_mode(size, flags)


def handle_window_event(pygame, event, canvas, window):
    """Handle shared F11 and Ctrl +/- window controls."""
    from .preferences import get_preferences, set_preferences
    preferences = get_preferences()
    resize_events = (pygame.VIDEORESIZE,
                     getattr(pygame, 'WINDOWRESIZED', pygame.VIDEORESIZE))
    if event.type in resize_events and not preferences['fullscreen']:
        width, height = getattr(event, 'size',
                                (getattr(event, 'x', window.get_width()),
                                 getattr(event, 'y', window.get_height())))
        scale = min(width / canvas.get_width(), height / canvas.get_height())
        set_preferences(window_size=[width, height],
                        scale=max(0.5, min(5.0, scale)))
        return pygame.display.get_surface() or window, False
    arrow_keys = (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)
    if event.type == pygame.KEYUP and event.key in arrow_keys:
        _held_arrows.pop(event.key, None)
    elif (event.type == pygame.KEYDOWN and event.key in arrow_keys and
          not getattr(event, 'navigation_repeat', False)):
        _held_arrows[event.key] = time.monotonic() + _REPEAT_DELAY
    if event.type != pygame.KEYDOWN:
        return window, False
    if event.key == pygame.K_F11:
        return toggle_fullscreen(pygame), True
    plus = event.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS)
    minus = event.key in (pygame.K_MINUS, pygame.K_KP_MINUS)
    if getattr(event, 'mod', 0) & pygame.KMOD_CTRL and (plus or minus):
        scale = round(preferences['scale'] + (0.1 if plus else -0.1), 2)
        scale = max(0.5, min(5.0, scale))
        return resize_window(pygame, canvas, scale), True
    return window, False


def present_scaled(pygame, canvas, window):
    """Scale the DOS canvas to the current (possibly resized) window."""
    now = time.monotonic()
    for key, deadline in tuple(_held_arrows.items()):
        if now >= deadline:
            pygame.event.post(pygame.event.Event(
                pygame.KEYDOWN, key=key, mod=pygame.key.get_mods(),
                unicode='', navigation_repeat=True))
            _held_arrows[key] = now + _REPEAT_INTERVAL
    window = pygame.display.get_surface() or window
    target_width, target_height = window.get_size()
    base_width, base_height = canvas.get_size()
    factor = min(target_width / base_width, target_height / base_height)
    scaled_size = (max(1, round(base_width * factor)), max(1, round(base_height * factor)))
    from .theme import COLORS
    window.fill(COLORS['background'])
    if scaled_size == canvas.get_size():
        scaled = canvas
    else:
        # Bilinear scaling keeps text and vector UI edges clean on high-DPI
        # screens and at non-integer window scales.
        scaled = pygame.transform.smoothscale(canvas, scaled_size)
    offset = ((target_width - scaled_size[0]) // 2, (target_height - scaled_size[1]) // 2)
    window.blit(scaled, offset)
    pygame.display.flip()
