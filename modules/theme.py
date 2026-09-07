"""Small, dependency-free visual theme shared by the pygame screens."""
from __future__ import annotations


DARK_COLORS = {
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
    "decor_top": (27, 64, 103),
    "decor_bottom": (17, 85, 84),
}

LIGHT_COLORS = {
    "background": (235, 241, 248),
    "background_alt": (224, 232, 242),
    "panel": (250, 252, 255),
    "panel_alt": (237, 243, 250),
    "border": (174, 190, 210),
    "text": (28, 42, 61),
    "muted": (91, 108, 130),
    "accent": (31, 112, 207),
    "accent_alt": (17, 139, 111),
    "warning": (177, 111, 20),
    "danger": (204, 55, 78),
    "buy": (12, 137, 94),
    "sell": (201, 73, 47),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "decor_top": (198, 221, 246),
    "decor_bottom": (194, 232, 222),
}

COLORS = dict(DARK_COLORS)


def apply_theme(name=None):
    from .preferences import get_preferences
    name = name or get_preferences()['theme']
    COLORS.clear()
    COLORS.update(LIGHT_COLORS if name == 'light' else DARK_COLORS)


def font(pygame, size: int, bold: bool = False):
    """Load a Unicode UI font with portable fallbacks."""
    from .preferences import get_preferences
    size = max(8, round(size * get_preferences()['font_scale']))
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


def back_button(pygame):
    return pygame.Rect(810, 31, 102, 34)


def draw_back_button(pygame, surface, typeface, caption='← Назад'):
    rect = back_button(pygame)
    rounded(pygame, surface, rect, COLORS['background_alt'], 8)
    rounded(pygame, surface, rect, COLORS['border'], 8, 1)
    label(pygame, surface, typeface, caption, (rect.x + 14, rect.y + 8),
          COLORS['text'])
    return rect


def draw_tooltip(pygame, surface, typeface, value, position):
    if not value or position is None:
        return
    rendered = typeface.render(str(value), True, COLORS['text'])
    rect = rendered.get_rect()
    rect.topleft = (min(position[0] + 14, surface.get_width() - rect.width - 20),
                    min(position[1] + 18, surface.get_height() - rect.height - 16))
    box = rect.inflate(18, 12)
    rounded(pygame, surface, box, COLORS['panel_alt'], 7)
    rounded(pygame, surface, box, COLORS['border'], 7, 1)
    surface.blit(rendered, rect)


def draw_confirmation(pygame, surface, body, title, heading, message,
                      selected=1):
    box = pygame.Rect(180, 196, 600, 210)
    rounded(pygame, surface, box, COLORS['panel_alt'], 16)
    rounded(pygame, surface, box, COLORS['danger'], 16, 2)
    label(pygame, surface, title, heading, (220, 226), COLORS['text'])
    label(pygame, surface, body, message, (220, 278), COLORS['muted'])
    yes = pygame.Rect(220, 330, 250, 46)
    no = pygame.Rect(490, 330, 250, 46)
    rounded(pygame, surface, yes,
            COLORS['danger'] if selected == 0 else COLORS['background_alt'], 9)
    rounded(pygame, surface, yes, COLORS['danger'], 9, 1)
    rounded(pygame, surface, no,
            COLORS['accent'] if selected == 1 else COLORS['background_alt'], 9)
    rounded(pygame, surface, no, COLORS['border'], 9, 1)
    if selected in (0, 1):
        choice = yes if selected == 0 else no
        rounded(pygame, surface, choice, COLORS['accent_alt'], 9, 3)
    label(pygame, surface, body, 'Выйти', (yes.x + 88, yes.y + 12),
          COLORS['white'] if selected == 0 else COLORS['danger'])
    label(pygame, surface, body, 'Продолжить', (no.x + 70, no.y + 12),
          COLORS['white'] if selected == 1 else COLORS['text'])
    label(pygame, surface, body, '← →  выбор · Enter  подтвердить',
          (box.x + 155, box.bottom - 18), COLORS['muted'])
    return yes, no
