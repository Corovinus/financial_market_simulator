"""FAST research build: modern menu, manual browser and teaching modules."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from market.levels import CUSTOM_LEVELS
from modules.document import document_lines, draw_document_line, table_of_contents
from modules.display import open_scaled_display, present_scaled
from modules.theme import COLORS, card, font, label, mouse_position, rounded

ROOT = Path(__file__).resolve().parent
LOG_PATH = ROOT / 'fast.log'
LOGGER = logging.getLogger('fast')


def configure_logging():
    """Write navigation and crash diagnostics without growing the file forever."""
    if LOGGER.handlers:
        return
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=2,
                                  encoding='utf-8')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s: %(message)s'))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def wrapped_index(current, delta, count):
    """Move inside a cyclic menu, safely handling an empty list."""
    return (current + delta) % count if count else 0


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
        ('Сетевая игра', [('Локальная сеть', '')]),
        ('Конец', []),
    ]


GROUPS = build_groups()


def main():
    global GROUPS
    configure_logging()
    GROUPS = build_groups()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, help='Save the initial menu and exit (SDL dummy supported).')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Scale BIDASK decisecond time (1 is original pace).')
    parser.add_argument('--scale', type=float, default=1.25,
                        help='Initial window scale (0.5..5); the window can also be resized.')
    args = parser.parse_args()
    import pygame as pg
    screen = None
    window = None
    typeface = None
    small = None
    heading = None
    formula = None
    document_heading = None
    table_font = None

    def reset_display():
        nonlocal screen, window, typeface, small, heading, formula, document_heading, table_font
        pg.init()
        screen, window = open_scaled_display(pg, (960, 600), args.scale,
                                              'FAST — исследовательская версия')
        typeface = font(pg, 18)
        small = font(pg, 14)
        heading = font(pg, 30, bold=True)
        formula = font(pg, 15)
        document_heading = font(pg, 22, bold=True)
        table_font = pg.font.SysFont('consolas', 12)

    reset_display()
    sections = json.loads((ROOT / 'data/converted/manual_sections.json').read_text(encoding='utf-8'))
    toc_entries = table_of_contents(sections['Оглавление'], sections)
    group = row = choice = scroll = horizontal = 0
    toc_index = toc_scroll = 0
    mode = 'main'
    lines = []
    reader_back = 'items'
    running = True
    clock = pg.time.Clock()
    sidebar_rects = [pg.Rect(36, 145 + index * 44, 208, 36)
                     for index in range(len(GROUPS))]
    open_button = pg.Rect(306, 474, 180, 42)
    back_button = pg.Rect(810, 31, 102, 34)
    reader_page_size = 16

    LOGGER.info('Application started: scale=%s speed=%s groups=%s',
                args.scale, args.speed, len(GROUPS))

    def text(value, x, y, color=None, face=None):
        label(pg, screen, face or typeface, value, (x, y), color or COLORS['text'])

    def item_rects():
        return [pg.Rect(306, 194 + index * 42, 600, 34)
                for index in range(len(GROUPS[group][1]))]

    def action_rects():
        return [pg.Rect(306, 282 + index * 58, 600, 44) for index in range(2)]

    def reader_limit():
        return max(0, len(lines) - 2)

    def description_lines(label_value, prefix):
        """Return a valid reader page even for a custom level."""
        if label_value == 'Локальная сеть':
            return [
                'Локальная сетевая игра', '',
                'Преподаватель создаёт комнату и наблюдает портфели игроков.',
                'Игрок-хост получает сбалансированный сценарий по случайному seed.',
                'Остальные студенты подключаются по адресу IP:порт.',
                'Все заявки проверяются одним сервером, поэтому книга общая.',
                'Расширенные настройки описаны в README.md.',
            ]
        title = next((name for name in sections if prefix and name.startswith(prefix)), None)
        if title:
            return [title, ''] + document_lines(sections[title])
        custom = next((level for level in CUSTOM_LEVELS if level.name == label_value), None)
        if custom:
            scenario = custom.scenario
            return [label_value, '',
                    f'Периодов: {scenario.periods}',
                    f'Длительность: {scenario.duration_ticks / 10:g} сек.',
                    'Инструменты: ' + ', '.join(scenario.names),
                    f'Начальные деньги: {scenario.cash:g}',
                    'Начальные позиции: ' + ', '.join(map(str, scenario.positions))]
        return [label_value, '', 'Описание для этого раздела пока недоступно.']

    def enter_section():
        nonlocal mode, row, choice
        items = GROUPS[group][1]
        if group == len(GROUPS) - 1:
            mode = 'exit'
        elif items:
            row, choice, mode = 0, 0, 'items'
        else:
            LOGGER.info('Empty section selected: group=%s', GROUPS[group][0])

    def set_group(index, source):
        nonlocal group, row, choice, mode
        group = index % len(GROUPS)
        row = choice = 0
        mode = 'main'
        LOGGER.info('Section selected via %s: index=%s name=%s',
                    source, group, GROUPS[group][0])

    def go_back():
        """Return one visible navigation level, just like Esc/Left."""
        nonlocal mode
        if mode == 'reader':
            mode = reader_back
        elif mode in ('action', 'toc'):
            mode = 'items'
        elif mode in ('items', 'exit'):
            mode = 'main'

    def open_selected():
        """Activate the currently selected menu item."""
        nonlocal mode, choice, lines, scroll, horizontal, reader_back
        if group == len(GROUPS) - 1:
            mode = 'exit'
            return
        if not GROUPS[group][1]:
            mode = 'main'
            return
        label_value, prefix = GROUPS[group][1][row]
        LOGGER.info('Item opened: group=%s row=%s label=%s',
                    GROUPS[group][0], row, label_value)
        if group == 1 and row == 1:
            from modules.introduction import run_introduction
            LOGGER.info('Module started: introduction')
            try:
                run_introduction(args.speed, args.scale, close_display=False)
            except Exception:
                LOGGER.exception('Module failed: introduction')
                raise
            reset_display()
            mode = 'main'
            pg.event.clear()
            LOGGER.info('Module closed: introduction; main display restored=%s',
                        pg.display.get_init())
            return
        if label_value == 'Оглавление':
            mode = 'toc'
            return
        if group >= 2:
            mode, choice = 'action', 0
            return
        lines = description_lines(label_value, prefix)
        reader_back = 'items'
        mode, scroll, horizontal = 'reader', 0, 0

    def activate_action():
        nonlocal mode, lines, scroll, horizontal, reader_back
        label_value, prefix = GROUPS[group][1][row]
        if choice == 0:
            lines = description_lines(label_value, prefix)
            reader_back = 'action'
            mode, scroll, horizontal = 'reader', 0, 0
            LOGGER.info('Description opened: %s', label_value)
            return
        LOGGER.info('Module started: %s', label_value)
        try:
            if label_value == 'Локальная сеть':
                from modules.network_launcher import run_network_launcher
                run_network_launcher(args.scale)
            elif label_value in ('Case B01', 'Case B02'):
                from modules.bidask import run_session
                run_session(ROOT / f'data/original/{label_value[5:]}.PAR',
                            args.speed, args.scale, close_display=False)
            else:
                custom = next((level for level in CUSTOM_LEVELS
                               if level.name == label_value), None)
                if custom is not None:
                    from modules.bidask import run_session
                    run_session(custom.scenario, args.speed, args.scale,
                                close_display=False)
                else:
                    from modules.workshops import run_module
                    run_module(label_value, args.speed, args.scale,
                               close_display=False)
        except Exception:
            LOGGER.exception('Module failed: %s', label_value)
            raise
        reset_display()
        mode = 'main'
        pg.event.clear()
        LOGGER.info('Module closed: %s; main display restored=%s',
                    label_value, pg.display.get_init())

    def click_action(position):
        """Make the menu usable with a mouse without changing keyboard flow."""
        nonlocal group, row, mode, choice, lines, scroll, horizontal
        nonlocal toc_index, toc_scroll, reader_back
        if position is None:
            return
        if mode != 'main' and back_button.collidepoint(position):
            go_back()
            return
        for index, rect in enumerate(sidebar_rects):
            if rect.collidepoint(position):
                set_group(index, 'mouse')
                enter_section()
                return
        if mode == 'main':
            for index, rect in enumerate(item_rects()[:6]):
                if rect.collidepoint(position):
                    row, mode = index, 'items'
                    return
            if open_button.collidepoint(position):
                enter_section()
        elif mode == 'items':
            for index, rect in enumerate(item_rects()):
                if rect.collidepoint(position):
                    row = index
                    LOGGER.info('Item selected via mouse: group=%s row=%s label=%s',
                                GROUPS[group][0], row, GROUPS[group][1][row][0])
                    return
            if open_button.collidepoint(position):
                open_selected()
        elif mode == 'action':
            selected = next((index for index, rect in enumerate(action_rects())
                             if rect.collidepoint(position)), None)
            if selected is not None:
                choice = selected
                LOGGER.info('Action clicked: item=%s choice=%s',
                            GROUPS[group][1][row][0], choice)
                activate_action()
        elif mode == 'toc':
            visible = toc_entries[toc_scroll:toc_scroll + 11]
            for offset, _title in enumerate(visible):
                rect = pg.Rect(306, 184 + offset * 30, 600, 26)
                if rect.collidepoint(position):
                    toc_index = toc_scroll + offset
                    target = toc_entries[toc_index]
                    lines = [target, ''] + document_lines(sections[target])
                    reader_back = 'toc'
                    mode, scroll, horizontal = 'reader', 0, 0
                    return

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                click_action(mouse_position(pg, event, window, screen))
                continue
            if event.type == pg.MOUSEWHEEL and mode == 'reader':
                scroll = max(0, min(reader_limit(), scroll - event.y * 3))
            elif event.type == pg.MOUSEWHEEL and mode == 'toc':
                toc_index = max(0, min(len(toc_entries) - 1,
                                       toc_index - event.y))
                toc_scroll = max(0, min(toc_index, len(toc_entries) - 11))
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
            if mode == 'reader':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = reader_back
                elif key in (pg.K_DOWN, pg.K_PAGEDOWN):
                    scroll = min(reader_limit(), scroll + (reader_page_size if key == pg.K_PAGEDOWN else 1))
                elif key in (pg.K_UP, pg.K_PAGEUP):
                    scroll = max(0, scroll - (reader_page_size if key == pg.K_PAGEUP else 1))
                elif key == pg.K_HOME:
                    scroll = 0
                elif key == pg.K_END:
                    scroll = reader_limit()
            elif mode == 'toc':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = 'items'
                elif key in (pg.K_UP, pg.K_DOWN):
                    toc_index = wrapped_index(
                        toc_index, 1 if key == pg.K_DOWN else -1,
                        len(toc_entries))
                    toc_scroll = min(max(0, toc_index - 10),
                                     max(0, len(toc_entries) - 11))
                elif key in (pg.K_RETURN, pg.K_RIGHT):
                    target = toc_entries[toc_index]
                    lines = [target, ''] + document_lines(sections[target])
                    reader_back = 'toc'
                    mode, scroll, horizontal = 'reader', 0, 0
            elif mode == 'exit':
                if key in (pg.K_RETURN, pg.K_y):
                    running = False
                elif key in (pg.K_ESCAPE, pg.K_n):
                    mode = 'main'
            elif mode == 'main':
                if key in (pg.K_UP, pg.K_DOWN):
                    set_group(wrapped_index(group, 1 if key == pg.K_DOWN else -1,
                                            len(GROUPS)), 'keyboard')
                elif key in (pg.K_RETURN, pg.K_RIGHT):
                    enter_section()
                elif key == pg.K_ESCAPE:
                    mode = 'exit'
            elif mode == 'items':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = 'main'
                elif key in (pg.K_UP, pg.K_DOWN):
                    row = wrapped_index(row, 1 if key == pg.K_DOWN else -1,
                                        len(GROUPS[group][1]))
                    LOGGER.info('Item selected via keyboard: group=%s row=%s',
                                GROUPS[group][0], row)
                elif key in (pg.K_RETURN, pg.K_RIGHT):
                    open_selected()
            elif mode == 'action':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = 'items'
                elif key in (pg.K_UP, pg.K_DOWN):
                    choice = wrapped_index(choice, 1 if key == pg.K_DOWN else -1, 2)
                    LOGGER.info('Action selected via keyboard: item=%s choice=%s',
                                GROUPS[group][1][row][0], choice)
                elif key in (pg.K_RETURN, pg.K_RIGHT):
                    activate_action()

        if not running:
            break
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (27, 64, 103), (850, 0), 260)
        pg.draw.circle(screen, (17, 85, 84), (720, 660), 220)
        rounded(pg, screen, pg.Rect(24, 20, 912, 58), COLORS['panel'], 16)
        text('FAST', 48, 30, COLORS['accent'], heading)
        text('Финансовая торговая система', 150, 38, COLORS['text'], typeface)
        if mode == 'main':
            text('Исследовательская версия', 720, 40, COLORS['muted'], small)
        else:
            rounded(pg, screen, back_button, COLORS['background_alt'], 8)
            rounded(pg, screen, back_button, COLORS['border'], 8, 1)
            text('← Назад', back_button.x + 14, back_button.y + 8,
                 COLORS['text'], small)

        sidebar = pg.Rect(24, 98, 232, 450)
        card(pg, screen, sidebar, COLORS['panel'], COLORS['border'])
        text('РАЗДЕЛЫ  ·  ↑ ↓', 44, 118, COLORS['muted'], small)
        for index, (group_label, _) in enumerate(GROUPS):
            rect = sidebar_rects[index]
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
            stage = {'main': '1 · РАЗДЕЛ', 'items': '2 · МАТЕРИАЛ', 'action': '3 · ДЕЙСТВИЕ'}[mode]
            text(stage, 790, 138, COLORS['accent_alt'], small)
            if mode == 'main':
                item_count = len(GROUPS[group][1])
                if group == len(GROUPS) - 1:
                    text('Завершение работы с программой', 308, 214, COLORS['muted'], typeface)
                    text('Enter или → — перейти к подтверждению', 308, 258, COLORS['danger'], typeface)
                elif item_count:
                    text('Материалы раздела', 308, 166, COLORS['muted'], small)
                    for value, rect in zip(
                            (item[0] for item in GROUPS[group][1][:6]),
                            item_rects()[:6]):
                        rounded(pg, screen, rect, COLORS['background_alt'], 8)
                        text(value, rect.x + 16, rect.y + 7,
                             COLORS['text'], typeface)
                    if item_count > 6:
                        text(f'и ещё {item_count - 6}…', 760, 452,
                             COLORS['muted'], small)
                else:
                    text('В этом разделе пока нет уровней', 308, 214, COLORS['warning'], typeface)
                    text('Добавьте уровень в market/levels.py', 308, 258, COLORS['muted'], typeface)
                if item_count or group == len(GROUPS) - 1:
                    rounded(pg, screen, open_button, COLORS['accent'], 9)
                    text('Выбрать  →', open_button.x + 22, open_button.y + 10,
                         COLORS['white'], typeface)
            elif mode == 'items':
                options = [item[0] for item in GROUPS[group][1]]
                text('↑ ↓ — выбрать материал   ← — назад', 308, 166, COLORS['muted'], small)
                for index, (value, rect) in enumerate(zip(options, item_rects())):
                    selected = index == row
                    rounded(pg, screen, rect, COLORS['accent'] if selected else COLORS['background_alt'], 8)
                    if selected:
                        pg.draw.rect(screen, COLORS['accent_alt'], (rect.x, rect.y, 4, rect.height), border_radius=2)
                    text(value, rect.x + 16, rect.y + 7, COLORS['white'] if selected else COLORS['text'], typeface)
                rounded(pg, screen, open_button, COLORS['accent'], 9)
                text('Открыть  →', open_button.x + 22, open_button.y + 10,
                     COLORS['white'], typeface)
            else:
                text(GROUPS[group][1][row][0], 308, 214, COLORS['accent_alt'], typeface)
                text('↑ ↓ — выбрать действие   ← — назад', 308, 254, COLORS['muted'], small)
                actions = (('Описание режима', 'Открыть сетевую игру')
                           if GROUPS[group][1][row][0] == 'Локальная сеть'
                           else ('Описание игры', 'Торговая сессия'))
                for index, (value, rect) in enumerate(zip(
                        actions, action_rects())):
                    rounded(pg, screen, rect, COLORS['accent'] if index == choice else COLORS['background_alt'], 10)
                    if index == choice:
                        pg.draw.rect(screen, COLORS['accent_alt'], (rect.x, rect.y, 4, rect.height), border_radius=2)
                    text(value, rect.x + 18, rect.y + 11, COLORS['white'], typeface)
        elif mode == 'reader':
            text((lines[0] if lines else 'Документ')[:58], 306, 130,
                 COLORS['text'], document_heading)
            text('PgUp/PgDn или колёсико — прокрутка', 308, 166, COLORS['muted'], small)
            y = 194
            for value in lines[1 + scroll:]:
                height = draw_document_line(
                    pg, screen, value, pg.Rect(302, y, 620, 44),
                    small, formula, table_font, COLORS)
                y += height
                if y > 520:
                    break
        elif mode == 'toc':
            text('Оглавление', 306, 126, COLORS['text'], heading)
            text('Выберите статью: ↑ ↓, Enter или клик мышью',
                 308, 162, COLORS['muted'], small)
            for offset, value in enumerate(toc_entries[toc_scroll:toc_scroll + 11]):
                index = toc_scroll + offset
                rect = pg.Rect(306, 184 + offset * 30, 600, 26)
                active = index == toc_index
                rounded(pg, screen, rect,
                        COLORS['accent'] if active else COLORS['background_alt'], 6)
                text(f'{index + 1:>2}. {value}'[:72], rect.x + 10, rect.y + 5,
                     COLORS['white'] if active else COLORS['text'], small)
        elif mode == 'exit':
            text('Завершить работу?', 306, 140, COLORS['text'], heading)
            text('Все открытые окна будут закрыты.', 308, 190, COLORS['muted'], typeface)
            rounded(pg, screen, pg.Rect(308, 264, 260, 48), COLORS['danger'], 10)
            text('Enter / Y — Да', 334, 277, COLORS['white'], typeface)
            rounded(pg, screen, pg.Rect(588, 264, 260, 48), COLORS['background_alt'], 10)
            text('Esc / N — Нет', 616, 277, COLORS['text'], typeface)
        rounded(pg, screen, pg.Rect(24, 562, 912, 24), COLORS['panel'], 8)
        footer = ('↑ ↓ разделы    Enter / → открыть    Esc выход' if mode == 'main' else
                  '↑ ↓ выбрать    Enter / → открыть    Esc / ← назад' if mode in ('items', 'action', 'toc') else
                  '↑ ↓ прокрутка    PgUp/PgDn страница    Esc / ← назад')
        text(footer + '    мышь поддерживается', 38, 566, COLORS['muted'], small)
        present_scaled(pg, screen, window)
        if args.screenshot:
            pg.image.save(window, args.screenshot)
            running = False
        clock.tick(30)
    pg.quit()
    LOGGER.info('Application closed normally')


if __name__ == '__main__':
    configure_logging()
    try:
        main()
    except Exception:
        LOGGER.exception('Unhandled application error')
        print(f'Произошла ошибка. Подробности записаны в {LOG_PATH}', file=sys.stderr)
        raise
