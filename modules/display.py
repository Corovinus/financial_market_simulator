"""Shared DOS text rendering helpers and logical-resolution scaling."""
from __future__ import annotations


_REPLACEMENTS = str.maketrans({
    "—": "-", "–": "-", "−": "-", "…": "...", "×": "x", "•": "*",
    "↑": "^", "↓": "v", "←": "<", "→": ">", "↔": "<>",
    "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'",
})


def cp866_bytes(value) -> bytes:
    """Encode text for the bundled CP866 bitmap, replacing non-DOS glyphs."""
    return str(value).translate(_REPLACEMENTS).encode("cp866", errors="replace")


def open_scaled_display(pygame, size, scale, caption):
    """Return a fixed-size pixel canvas and a resizable scaled window."""
    if not isinstance(scale, (int, float)) or not 0.5 <= float(scale) <= 5:
        raise ValueError("Масштаб должен быть числом от 0.5 до 5")
    base_size = (int(size[0]), int(size[1]))
    window_size = tuple(max(1, round(value * float(scale))) for value in base_size)
    window = pygame.display.set_mode(window_size, pygame.RESIZABLE)
    pygame.display.set_caption(caption)
    return pygame.Surface(base_size), window


def present_scaled(pygame, canvas, window):
    """Scale the DOS canvas to the current (possibly resized) window."""
    window = pygame.display.get_surface() or window
    target_width, target_height = window.get_size()
    base_width, base_height = canvas.get_size()
    factor = min(target_width / base_width, target_height / base_height)
    scaled_size = (max(1, round(base_width * factor)), max(1, round(base_height * factor)))
    window.fill((0, 0, 0))
    if scaled_size == canvas.get_size():
        scaled = canvas
    else:
        # Bilinear scaling keeps text and vector UI edges clean on high-DPI
        # screens and at non-integer window scales.
        scaled = pygame.transform.smoothscale(canvas, scaled_size)
    offset = ((target_width - scaled_size[0]) // 2, (target_height - scaled_size[1]) // 2)
    window.blit(scaled, offset)
    pygame.display.flip()
