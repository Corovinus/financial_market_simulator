"""Renderer for trading assignments and their live progress."""
from .theme import COLORS, card, label, rounded


def draw_goals(pygame, screen, progress, player_name, selected, faces,
               can_switch=True):
    body, small, title = faces

    def write(value, x, y, color=None, face=None):
        label(pygame, screen, face or body, value, (x, y),
              color or COLORS['text'])

    screen.fill(COLORS['background'])
    pygame.draw.circle(screen, (27, 64, 103), (900, 0), 260)
    rounded(pygame, screen, pygame.Rect(24, 18, 912, 58),
            COLORS['panel'], 15)
    write('Учебные цели', 48, 30, COLORS['accent'], title)
    write(player_name[:28], 710, 38, COLORS['muted'], small)
    finished = progress['finished']
    heading = ('Все цели выполнены' if progress['all_passed'] else
               'Есть невыполненные цели') if finished else 'Текущий прогресс'
    heading_color = (COLORS['buy'] if progress['all_passed'] else
                     COLORS['sell']) if finished else COLORS['warning']
    write(heading, 48, 104, heading_color, body)
    write(f'Прогноз капитала: {progress["capital"]:.2f}', 650, 108,
          COLORS['accent_alt'], small)

    items = progress['items']
    selected = max(0, min(selected, max(0, len(items) - 1)))
    start = min(max(0, selected - 4), max(0, len(items) - 6))
    for offset, item in enumerate(items[start:start + 6]):
        index = start + offset
        rect = pygame.Rect(48, 150 + offset * 62, 864, 50)
        active = index == selected
        card(pygame, screen, rect,
             COLORS['panel_alt'] if active else COLORS['panel'],
             COLORS['accent'] if active else COLORS['border'], 10)
        color = COLORS['buy'] if item['passed'] else COLORS['sell']
        write('OK' if item['passed'] else '—', rect.x + 14, rect.y + 12,
              color, small)
        write(item['label'][:67], rect.x + 52, rect.y + 8,
              COLORS['text'], small)
        state = ('Выполнено' if item['passed'] else 'Не выполнено')
        if not finished:
            state = ('Сейчас выполнено' if item['passed'] else 'Пока не выполнено')
        write(f'{item["progress"]} · {state}', rect.x + 52, rect.y + 27,
              color, small)

    rounded(pygame, screen, pygame.Rect(24, 530, 912, 52),
            COLORS['panel'], 10)
    controls = '↑ ↓ цель · '
    if can_switch:
        controls += 'Tab участник · '
    controls += 'F4/Esc закрыть'
    write(controls, 46, 549, COLORS['muted'], small)
