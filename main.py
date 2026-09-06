"""FAST research build: DOS-like menu/manual browser and teaching modules."""
import argparse
import json
from pathlib import Path

from market.levels import CUSTOM_LEVELS
from modules.display import open_scaled_display, present_scaled
from modules.theme import COLORS, card, centered, font, label, mouse_position, rounded

ROOT = Path(__file__).resolve().parent


def build_groups():
    return [
        ('Информация', [('Оглавление', 'Оглавление'),
                        ('Программа FAST', 'Программа F A S T')]),
        ('Торги', [('Инструкция', 'Описание Торговой Системы'),
                   ('Знакомство', 'Знакомство с двойным аукционом')]),
        ('Облигации', [(f'Case B0{i}', f'Описание B0{i}') for i in range(1, 5)] + [('Дюрация', 'Описание TutBO')]),
        ('Акции', [(f'Case CA{i}', f'Описание CA{i}') for i in range(1, 4)] + [('Портфель акций', 'Описание TutCAPM')]),
        ('Опционы', [(f'Case OP{i}', f'Описание OP{i}') for i in range(1, 4)] + [('Опционы', 'Описание TutOP')]),
        ('Эффективность', [(f'Case RE{i}', f'Описание RE{i}') for i in range(1, 4)]),
        ('Свои уровни', [(level.name, '') for level in CUSTOM_LEVELS]),
        ('Конец', []),
    ]


GROUPS = build_groups()


def main():
    global GROUPS
    GROUPS = build_groups()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, help='Save the initial menu and exit (SDL dummy supported).')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Scale BIDASK decisecond time (1 is original pace).')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='Initial window scale (0.5..5); the window can also be resized.')
    args = parser.parse_args()
    import pygame as pg
    screen = None
    window = None
    typeface = None
    small = None
    heading = None

    def reset_display():
        nonlocal screen, window, typeface, small, heading
        pg.init()
        screen, window = open_scaled_display(pg, (960, 600), args.scale,
                                              'FAST — исследовательская версия')
        typeface = font(pg, 18)
        small = font(pg, 14)
        heading = font(pg, 30, bold=True)

    reset_display()
    sections = json.loads((ROOT / 'data/converted/manual_sections.json').read_text(encoding='utf-8'))
    group = row = choice = scroll = horizontal = 0
    mode = 'main'
    lines = []
    running = True
    clock = pg.time.Clock()

    def text(value, x, y, color=None, face=None):
        label(pg, screen, face or typeface, value, (x, y), color or COLORS['text'])

    def open_selected():
        """Activate the currently selected menu item."""
        nonlocal mode, choice, lines, scroll, horizontal
        if group == len(GROUPS) - 1:
            mode = 'exit'
            return
        label_value, prefix = GROUPS[group][1][row]
        if group == 1 and row == 1:
            from modules.introduction import run_introduction
            run_introduction(args.speed, args.scale)
            reset_display()
            mode = 'main'
            return
        if group >= 2:
            mode, choice = 'action', 0
            return
        title = next(name for name in sections if name.startswith(prefix))
        lines = [title, ''] + sections[title].replace('`', '').replace('|', '').splitlines()
        mode, scroll, horizontal = 'reader', 0, 0

    def click_action(position):
        """Make the menu usable with a mouse without changing keyboard flow."""
        nonlocal group, row, mode, choice, lines, scroll, horizontal
        if position is None:
            return
        x, y = position
        if 24 <= x <= 250 and 92 <= y <= 92 + 48 * len(GROUPS):
            selected = (y - 92) // 48
            if 0 <= selected < len(GROUPS):
                group, row, mode = selected, 0, 'main'
            return
        if mode == 'main' and 284 <= x <= 936 and 176 <= y <= 176 + 52 * max(1, len(GROUPS[group][1])):
            row = max(0, min(len(GROUPS[group][1]) - 1, (y - 176) // 52))
            mode = 'items'
        elif mode == 'items' and 300 <= x <= 920:
            selected = (y - 176) // 52
            if 0 <= selected < len(GROUPS[group][1]):
                row = selected
                open_selected()
        elif mode == 'action' and 300 <= x <= 920 and 270 <= y <= 390:
            choice = 0 if y < 330 else 1
            if choice == 0:
                label_value, prefix = GROUPS[group][1][row]
                title = next(name for name in sections if name.startswith(prefix))
                lines = [title, ''] + sections[title].replace('`', '').replace('|', '').splitlines()
                mode, scroll, horizontal = 'reader', 0, 0
            else:
                pg.event.post(pg.event.Event(pg.KEYDOWN, {'key': pg.K_RETURN}))

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                click_action(mouse_position(pg, event, window, screen))
                continue
            if event.type == pg.MOUSEWHEEL and mode == 'reader':
                scroll = max(0, min(max(0, len(lines) - 20), scroll - event.y * 3))
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
            if mode == 'reader':
                if key == pg.K_ESCAPE:
                    mode = 'action' if group >= 2 else 'items'
                elif key in (pg.K_DOWN, pg.K_PAGEDOWN):
                    scroll = min(max(0, len(lines) - 20), scroll + (20 if key == pg.K_PAGEDOWN else 1))
                elif key in (pg.K_UP, pg.K_PAGEUP):
                    scroll = max(0, scroll - (20 if key == pg.K_PAGEUP else 1))
                elif key == pg.K_HOME:
                    scroll = 0
                elif key == pg.K_END:
                    scroll = max(0, len(lines) - 20)
                elif key in (pg.K_LEFT, pg.K_RIGHT):
                    horizontal = max(0, min(max(0, max(map(len, lines), default=0) - 76), horizontal + (4 if key == pg.K_RIGHT else -4)))
            elif mode == 'exit':
                if key in (pg.K_RETURN, pg.K_y):
                    running = False
                elif key in (pg.K_ESCAPE, pg.K_n):
                    mode = 'main'
            elif mode == 'main':
                if key in (pg.K_LEFT, pg.K_RIGHT):
                    group = (group + (1 if key == pg.K_RIGHT else -1)) % len(GROUPS)
                elif key in (pg.K_RETURN, pg.K_DOWN):
                    row = choice = 0
                    mode = 'exit' if group == len(GROUPS) - 1 else 'items'
                elif key == pg.K_ESCAPE:
                    mode = 'exit'
            elif key == pg.K_ESCAPE:
                mode = 'items' if mode == 'action' else 'main'
            elif key in (pg.K_UP, pg.K_DOWN):
                delta = 1 if key == pg.K_DOWN else -1
                if mode == 'items':
                    row = (row + delta) % len(GROUPS[group][1])
                else:
                    choice = (choice + delta) % 2
            elif key == pg.K_RETURN:
                if mode == 'items' and group >= 2:
                    mode, choice = 'action', 0
                else:
                    if mode == 'action' and choice == 1:
                        label_value = GROUPS[group][1][row][0]
                        if label_value in ('Case B01', 'Case B02'):
                            from modules.bidask import run_session
                            run_session(ROOT / f'data/original/{label_value[5:]}.PAR', args.speed, args.scale)
                            reset_display()
                            mode = 'main'
                            continue
                        custom = next((level for level in CUSTOM_LEVELS if level.name == label_value), None)
                        if custom is not None:
                            from modules.bidask import run_session
                            run_session(custom.scenario, args.speed, args.scale)
                            reset_display()
                            mode = 'main'
                            continue
                        from modules.workshops import run_module
                        run_module(label_value, args.speed, args.scale)
                        reset_display()
                        mode = 'main'
                        continue
                    else:
                        label_value, prefix = GROUPS[group][1][row]
                        title = next(name for name in sections if name.startswith(prefix))
                        lines = [title, ''] + sections[title].replace('`', '').replace('|', '').splitlines()
                    mode, scroll, horizontal = 'reader', 0, 0

        if not running:
            break
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (27, 64, 103), (850, 0), 260)
        pg.draw.circle(screen, (17, 85, 84), (720, 660), 220)
        rounded(pg, screen, pg.Rect(24, 20, 912, 58), COLORS['panel'], 16)
        text('FAST', 48, 30, COLORS['accent'], heading)
        text('Финансовая торговая система', 150, 38, COLORS['text'], typeface)
        text('Исследовательская версия', 720, 40, COLORS['muted'], small)

        sidebar = pg.Rect(24, 98, 232, 450)
        card(pg, screen, sidebar, COLORS['panel'], COLORS['border'])
        text('РАЗДЕЛЫ', 44, 118, COLORS['muted'], small)
        for index, (group_label, _) in enumerate(GROUPS):
            rect = pg.Rect(36, 145 + index * 44, 208, 36)
            selected = index == group
            rounded(pg, screen, rect, COLORS['accent'] if selected else COLORS['panel'], 9)
            if selected:
                pg.draw.rect(screen, COLORS['accent_alt'], (36, rect.y, 4, rect.height), border_radius=2)
            text(group_label, 52, rect.y + 8, COLORS['white'] if selected else COLORS['muted'], typeface)

        content = pg.Rect(276, 98, 660, 450)
        card(pg, screen, content, COLORS['panel'], COLORS['border'])
        if mode in ('main', 'items', 'action'):
            title = GROUPS[group][0]
            text(title, 306, 126, COLORS['text'], heading)
            text('Выберите раздел клавишами или мышью', 308, 166, COLORS['muted'], small)
            if mode == 'main':
                item_count = len(GROUPS[group][1])
                text(f'{item_count} доступных материалов', 308, 222, COLORS['accent_alt'], typeface)
                text('Enter или ↓ — открыть содержимое', 308, 270, COLORS['muted'], typeface)
                text('← → — сменить раздел', 308, 302, COLORS['muted'], typeface)
                rounded(pg, screen, pg.Rect(308, 360, 580, 86), COLORS['background_alt'], 12)
                text('Сохранённое управление', 330, 382, COLORS['warning'], typeface)
                text('Клавиатура остаётся главным способом работы.', 330, 414, COLORS['text'], small)
            elif mode == 'items':
                options = [item[0] for item in GROUPS[group][1]]
                for index, value in enumerate(options):
                    rect = pg.Rect(306, 194 + index * 42, 600, 34)
                    selected = index == row
                    rounded(pg, screen, rect, COLORS['accent'] if selected else COLORS['background_alt'], 8)
                    text(value, rect.x + 16, rect.y + 7, COLORS['white'] if selected else COLORS['text'], typeface)
            else:
                text(GROUPS[group][1][row][0], 308, 214, COLORS['accent_alt'], typeface)
                text('Что открыть?', 308, 254, COLORS['muted'], small)
                for index, value in enumerate(('Описание игры', 'Торговая сессия')):
                    rect = pg.Rect(306, 282 + index * 58, 600, 44)
                    rounded(pg, screen, rect, COLORS['accent'] if index == choice else COLORS['background_alt'], 10)
                    text(value, rect.x + 18, rect.y + 11, COLORS['white'], typeface)
        elif mode == 'reader':
            text(lines[0] if lines else 'Документ', 306, 126, COLORS['text'], heading)
            text('PgUp/PgDn или колёсико — прокрутка', 308, 166, COLORS['muted'], small)
            for index, value in enumerate(lines[scroll + 1:scroll + 25]):
                text(value[horizontal:horizontal + 86], 308, 196 + index * 20, COLORS['text'], small)
        elif mode == 'exit':
            text('Завершить работу?', 306, 140, COLORS['text'], heading)
            text('Все открытые окна будут закрыты.', 308, 190, COLORS['muted'], typeface)
            rounded(pg, screen, pg.Rect(308, 264, 260, 48), COLORS['danger'], 10)
            text('Enter / Y — Да', 334, 277, COLORS['white'], typeface)
            rounded(pg, screen, pg.Rect(588, 264, 260, 48), COLORS['background_alt'], 10)
            text('Esc / N — Нет', 616, 277, COLORS['text'], typeface)
        rounded(pg, screen, pg.Rect(24, 562, 912, 24), COLORS['panel'], 8)
        text('Enter открыть    Esc назад    ↑ ↓ выбрать    ← → разделы    мышь — выделение', 38, 566, COLORS['muted'], small)
        present_scaled(pg, screen, window)
        if args.screenshot:
            pg.image.save(window, args.screenshot)
            running = False
        clock.tick(30)
    pg.quit()


if __name__ == '__main__':
    main()
