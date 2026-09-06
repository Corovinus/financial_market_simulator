"""Small, dependency-free visual theme shared by the pygame screens."""
from __future__ import annotations


COLORS = {
    "background": (11, 18, 32),
    "background_alt": (15, 25, 43),
    "panel": (25, 36, 57),
    "panel_alt": (31, 45, 70),
    "border": (61, 81, 112),
    "text": (232, 238, 248),
    "muted": (153, 169, 192),
    "accent": (78, 166, 255),
    "accent_alt": (102, 224, 190),
    "warning": (250, 190, 92),
    "danger": (255, 107, 129),
    "buy": (83, 211, 163),
    "sell": (255, 139, 111),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
}


def font(pygame, size: int, bold: bool = False):
    """Load a Unicode UI font with portable fallbacks."""
    names = ("segoeui", "dejavusans", "arial", "liberationsans")
    for name in names:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def rounded(pygame, surface, rect, color, radius: int = 12, width: int = 0):
    pygame.draw.rect(surface, color, rect, width, border_radius=radius)


def card(pygame, surface, rect, fill=None, border=None, radius: int = 14):
    rounded(pygame, surface, rect, fill or COLORS["panel"], radius)
    if border:
        rounded(pygame, surface, rect, border, radius, 1)


def label(pygame, surface, typeface, value, position, color=None):
    surface.blit(typeface.render(str(value), True, color or COLORS["text"]), position)


def mouse_position(pygame, event, window, canvas):
    """Convert a resizable-window mouse position to logical canvas pixels."""
    if not hasattr(event, "pos"):
        return None
    window = pygame.display.get_surface() or window
    width, height = window.get_size()
    base_width, base_height = canvas.get_size()
    factor = min(width / base_width, height / base_height)
    scaled = (base_width * factor, base_height * factor)
    offset = ((width - scaled[0]) / 2, (height - scaled[1]) / 2)
    x = (event.pos[0] - offset[0]) / factor
    y = (event.pos[1] - offset[1]) / factor
    if 0 <= x < base_width and 0 <= y < base_height:
        return int(x), int(y)
    return None
