"""FAST research build: modern menu, manual browser and teaching modules."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

from market.levels import CUSTOM_LEVELS, load_levels
from modules.document import (document_lines, draw_document_line, load_sections,
                              page_scroll, table_of_contents)
from modules.display import (handle_window_event, open_scaled_display,
                             present_scaled, resize_window,
                             toggle_fullscreen)
from modules.preferences import get_preferences, set_preferences
from modules.theme import (COLORS, apply_theme, card, draw_tooltip, font,
                           label, mouse_position, rounded)

ROOT = Path(__file__).resolve().parent
APP_ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else ROOT
LOG_PATH = APP_ROOT / 'fast.log'
LOGGER = logging.getLogger('fast')


def configure_logging():
    """Write navigation and crash diagnostics without growing the file forever."""
    global LOG_PATH
    if LOGGER.handlers:
        return
    try:
        handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=2,
                                      encoding='utf-8')
    except OSError:
        log_folder = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'FAST'
        log_folder.mkdir(parents=True, exist_ok=True)
        LOG_PATH = log_folder / 'fast.log'
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


def build_groups(custom_levels=None):
    custom_levels = CUSTOM_LEVELS if custom_levels is None else custom_levels
    return [
        ('Информация', [('Оглавление', 'Оглавление'),
                        ('Программа FAST', 'Программа F A S T')]),
        ('Торги', [('Инструкция', 'Описание Торговой Системы'),
                   ('Знакомство', 'Знакомство с двойным аукционом')]),
        ('Облигации', [(f'Case B0{i}', f'Описание B0{i}') for i in range(1, 5)] + [('Дюрация', 'Описание TutBO')]),
        ('Акции', [(f'Case CA{i}', f'Описание CA{i}') for i in range(1, 4)] + [('Портфель акций', 'Описание TutCAPM')]),
        ('Опционы', [(f'Case OP{i}', f'Описание OP{i}') for i in range(1, 4)] + [('Опционы', 'Описание TutOP')]),
        ('Эффективность', [(f'Case RE{i}', f'Описание RE{i}') for i in range(1, 4)]),
        ('Свои уровни', [(level.name, '') for level in custom_levels]),
        ('Сетевая игра', [('Локальная сеть', '')]),
        ('Настройки', []),
        ('Конец', []),
    ]


GROUPS = build_groups()


def main():
    global GROUPS
    configure_logging()
    try:
        active_levels = [*CUSTOM_LEVELS, *load_levels(APP_ROOT / 'levels.json')]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        LOGGER.exception('Failed to load levels.json')
        active_levels = list(CUSTOM_LEVELS)
    GROUPS = build_groups(active_levels)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, help='Save the initial menu and exit (SDL dummy supported).')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='Scale BIDASK decisecond time (1 is original pace).')
    parser.add_argument('--scale', type=float,
                        help='Initial window scale (0.5..5); the window can also be resized.')
    args = parser.parse_args()
    preferences = get_preferences()
    if args.scale is not None:
        if not 0.5 <= args.scale <= 5:
            parser.error('--scale должен быть от 0.5 до 5')
        set_preferences(scale=args.scale,
                        window_size=[round(960 * args.scale),
                                     round(600 * args.scale)],
                        fullscreen=False)
    else:
        args.scale = preferences['scale']
    import pygame as pg
    screen = None
    window = None
    typeface = None
    small = None
    heading = None
    formula = None
    document_heading = None
    table_font = None

    def reset_display(initial_scale=None):
        nonlocal screen, window, typeface, small, heading, formula, document_heading, table_font
        pg.init()
        screen, window = open_scaled_display(pg, (960, 600),
                                              args.scale if initial_scale is None else initial_scale,
                                              'FAST — исследовательская версия')
        typeface = font(pg, 18)
        small = font(pg, 14)
        heading = font(pg, 30, bold=True)
        formula = font(pg, 15)
        document_heading = font(pg, 22, bold=True)
        table_font = pg.font.SysFont(
            'consolas', round(12 * get_preferences()['font_scale']))

    reset_display()
    sections = load_sections(ROOT / 'data/converted/manual_sections.json')
    toc_entries = table_of_contents(sections['Оглавление'], sections)
    group = row = choice = scroll = item_scroll = 0
    toc_index = toc_scroll = 0
    mode = 'main'
    lines = []
    reader_back = 'items'
    running = True
    clock = pg.time.Clock()
    sidebar_rects = [pg.Rect(36, 145 + index * 40, 208, 32)
                     for index in range(len(GROUPS))]
    open_button = pg.Rect(306, 474, 180, 42)
    back_button = pg.Rect(810, 31, 102, 34)
    item_page_size = 6
    settings_index = 0
    hotkeys_back = 'settings'
    mouse = None
    setting_rows = (
        ('Тема', 'theme'), ('Размер шрифта', 'font_scale'),
        ('Звук', 'sound'), ('Масштаб окна', 'scale'),
        ('Полноэкранный режим', 'fullscreen'),
        ('Горячие клавиши', 'hotkeys'),
    )

    LOGGER.info('Application started: scale=%s speed=%s groups=%s',
                get_preferences()['scale'], args.speed, len(GROUPS))

    def text(value, x, y, color=None, face=None):
        label(pg, screen, face or typeface, value, (x, y), color or COLORS['text'])

    def item_rects():
        return [pg.Rect(306, 194 + index * 42, 600, 34)
                for index in range(item_page_size)]

    def keep_item_visible():
        nonlocal item_scroll
        if row < item_scroll:
            item_scroll = row
        elif row >= item_scroll + item_page_size:
            item_scroll = row - item_page_size + 1

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
        custom = next((level for level in active_levels if level.name == label_value), None)
        if custom:
            scenario = custom.scenario
            return [label_value, '',
                    f'Периодов: {scenario.periods}',
                    f'Длительность: {scenario.duration_ticks / 10:g} сек.',
                    'Инструменты: ' + ', '.join(scenario.names),
                    f'Начальные деньги: {scenario.cash:g}',
                    'Начальные позиции: ' + ', '.join(map(str, scenario.positions)),
                    f'Учебных целей: {len(scenario.goals)}']
        return [label_value, '', 'Описание для этого раздела пока недоступно.']

    def enter_section():
        nonlocal mode, row, choice, item_scroll, running
        items = GROUPS[group][1]
        if GROUPS[group][0] == 'Конец':
            running = False
        elif GROUPS[group][0] == 'Настройки':
            mode = 'settings'
        elif items:
            row, choice, item_scroll, mode = 0, 0, 0, 'items'
        else:
            LOGGER.info('Empty section selected: group=%s', GROUPS[group][0])

    def set_group(index, source):
        nonlocal group, row, choice, item_scroll, mode
        group = index % len(GROUPS)
        row = choice = item_scroll = 0
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
        elif mode in ('items', 'settings'):
            mode = 'main'
        elif mode == 'hotkeys':
            mode = hotkeys_back

    def change_preference(delta=0):
        nonlocal window, settings_index
        key = setting_rows[settings_index][1]
        values = get_preferences()
        if key == 'theme':
            theme = 'light' if values['theme'] == 'dark' else 'dark'
            set_preferences(theme=theme)
            apply_theme(theme)
        elif key == 'font_scale':
            value = max(0.8, min(1.2, round(values[key] + delta * .1, 1)))
            set_preferences(font_scale=value)
            reset_display()
        elif key == 'sound':
            set_preferences(sound=not values['sound'])
        elif key == 'scale':
            window = resize_window(pg, screen, values['scale'] + delta * .1)
        elif key == 'fullscreen':
            window = toggle_fullscreen(pg)
        else:
            mode_value = 'hotkeys'
            return mode_value
        return None

    def open_selected():
        """Activate the currently selected menu item."""
        nonlocal mode, choice, lines, scroll, reader_back
        if GROUPS[group][0] == 'Конец':
            mode = 'main'
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
            module_scale = get_preferences()['scale']
            try:
                run_introduction(args.speed, module_scale, close_display=False)
            except Exception:
                LOGGER.exception('Module failed: introduction')
                raise
            reset_display(module_scale)
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
        mode, scroll = 'reader', 0

    def activate_action():
        nonlocal mode, lines, scroll, reader_back
        label_value, prefix = GROUPS[group][1][row]
        if choice == 0:
            lines = description_lines(label_value, prefix)
            reader_back = 'action'
            mode, scroll = 'reader', 0
            LOGGER.info('Description opened: %s', label_value)
            return
        LOGGER.info('Module started: %s', label_value)
        module_scale = get_preferences()['scale']
        try:
            if label_value == 'Локальная сеть':
                from modules.network_launcher import run_network_launcher
                run_network_launcher(module_scale)
            elif label_value in ('Case B01', 'Case B02'):
                from modules.bidask import run_session
                run_session(ROOT / f'data/original/{label_value[5:]}.PAR',
                            args.speed, module_scale, close_display=False)
            else:
                custom = next((level for level in active_levels
                               if level.name == label_value), None)
                if custom is not None:
                    from modules.bidask import run_session
                    run_session(custom.scenario, args.speed, module_scale,
                                close_display=False)
                else:
                    from modules.workshops import run_module
                    run_module(label_value, args.speed, module_scale,
                               close_display=False)
        except Exception:
            LOGGER.exception('Module failed: %s', label_value)
            raise
        reset_display(module_scale)
        mode = 'main'
        pg.event.clear()
        LOGGER.info('Module closed: %s; main display restored=%s',
                    label_value, pg.display.get_init())

    def click_action(position):
        """Make the menu usable with a mouse without changing keyboard flow."""
        nonlocal group, row, item_scroll, mode, choice, lines, scroll
        nonlocal toc_index, toc_scroll, reader_back, running, settings_index
        nonlocal hotkeys_back
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
            for offset, rect in enumerate(item_rects()):
                index = item_scroll + offset
                if index >= len(GROUPS[group][1]):
                    break
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
                    mode, scroll = 'reader', 0
                    return
        elif mode == 'settings':
            for index, _setting in enumerate(setting_rows):
                if pg.Rect(306, 196 + index * 46, 600, 40).collidepoint(position):
                    settings_index = index
                    target = change_preference(1)
                    if target:
                        hotkeys_back = 'settings'
                        mode = target
                    return

    while running:
        for event in pg.event.get():
            window, handled = handle_window_event(pg, event, screen, window)
            if handled:
                continue
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEMOTION:
                mouse = mouse_position(pg, event, window, screen)
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                click_action(mouse_position(pg, event, window, screen))
                continue
            if event.type == pg.MOUSEWHEEL and mode == 'reader':
                scroll = max(0, min(reader_limit(), scroll - event.y * 3))
            elif event.type == pg.MOUSEWHEEL and mode == 'items':
                row = wrapped_index(row, -event.y, len(GROUPS[group][1]))
                keep_item_visible()
            elif event.type == pg.MOUSEWHEEL and mode == 'toc':
                toc_index = max(0, min(len(toc_entries) - 1,
                                       toc_index - event.y))
                toc_scroll = max(0, min(toc_index, len(toc_entries) - 11))
            if event.type != pg.KEYDOWN:
                continue
            key = event.key
            if key == pg.K_F1:
                if mode == 'hotkeys':
                    mode = hotkeys_back
                else:
                    hotkeys_back, mode = mode, 'hotkeys'
                continue
            if mode == 'reader':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = reader_back
                elif key in (pg.K_DOWN, pg.K_PAGEDOWN):
                    scroll = (page_scroll(lines[1:], scroll, 1, 326)
                              if key == pg.K_PAGEDOWN else
                              min(reader_limit(), scroll + 1))
                elif key in (pg.K_UP, pg.K_PAGEUP):
                    scroll = (page_scroll(lines[1:], scroll, -1, 326)
                              if key == pg.K_PAGEUP else max(0, scroll - 1))
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
                    mode, scroll = 'reader', 0
            elif mode == 'hotkeys':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = hotkeys_back
            elif mode == 'settings':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = 'main'
                elif key in (pg.K_UP, pg.K_DOWN):
                    settings_index = wrapped_index(
                        settings_index, 1 if key == pg.K_DOWN else -1,
                        len(setting_rows))
                elif key in (pg.K_LEFT, pg.K_RIGHT, pg.K_RETURN):
                    delta = -1 if key == pg.K_LEFT else 1
                    target = change_preference(delta)
                    if target:
                        hotkeys_back = 'settings'
                        mode = target
            elif mode == 'main':
                if key in (pg.K_UP, pg.K_DOWN):
                    set_group(wrapped_index(group, 1 if key == pg.K_DOWN else -1,
                                            len(GROUPS)), 'keyboard')
                elif key in (pg.K_RETURN, pg.K_RIGHT):
                    enter_section()
                elif key == pg.K_ESCAPE:
                    running = False
            elif mode == 'items':
                if key in (pg.K_ESCAPE, pg.K_LEFT):
                    mode = 'main'
                elif key in (pg.K_UP, pg.K_DOWN):
                    row = wrapped_index(row, 1 if key == pg.K_DOWN else -1,
                                        len(GROUPS[group][1]))
                    keep_item_visible()
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
        pg.draw.circle(screen, COLORS['decor_top'], (850, 0), 260)
        pg.draw.circle(screen, COLORS['decor_bottom'], (720, 660), 220)
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
                if GROUPS[group][0] == 'Конец':
                    text('Завершение работы с программой', 308, 214, COLORS['muted'], typeface)
                    text('Enter или → — закрыть программу', 308, 258, COLORS['danger'], typeface)
                elif GROUPS[group][0] == 'Настройки':
                    text('Оформление, окно, звук и управление', 308, 214,
                         COLORS['muted'], typeface)
                    text('Enter или → — открыть настройки', 308, 258,
                         COLORS['accent_alt'], typeface)
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
                if item_count or GROUPS[group][0] in ('Настройки', 'Конец'):
                    rounded(pg, screen, open_button, COLORS['accent'], 9)
                    button_label = ('Завершить →' if GROUPS[group][0] == 'Конец'
                                    else 'Выбрать  →')
                    text(button_label, open_button.x + 22, open_button.y + 10,
                         COLORS['white'], typeface)
            elif mode == 'items':
                options = [item[0] for item in GROUPS[group][1]]
                text('↑ ↓ — выбрать материал   ← — назад', 308, 166, COLORS['muted'], small)
                visible = options[item_scroll:item_scroll + item_page_size]
                for offset, (value, rect) in enumerate(zip(visible, item_rects())):
                    index = item_scroll + offset
                    selected = index == row
                    rounded(pg, screen, rect, COLORS['accent'] if selected else COLORS['background_alt'], 8)
                    if selected:
                        pg.draw.rect(screen, COLORS['accent_alt'], (rect.x, rect.y, 4, rect.height), border_radius=2)
                    text(value, rect.x + 16, rect.y + 7, COLORS['white'] if selected else COLORS['text'], typeface)
                if len(options) > item_page_size:
                    text(f'{row + 1} / {len(options)}', 828, 446,
                         COLORS['muted'], small)
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
        elif mode == 'settings':
            text('Настройки', 306, 126, COLORS['text'], heading)
            text('Изменения сохраняются автоматически', 308, 170,
                 COLORS['muted'], small)
            values = get_preferences()
            shown_values = {
                'theme': 'Светлая' if values['theme'] == 'light' else 'Тёмная',
                'font_scale': f'{values["font_scale"]:.0%}',
                'sound': 'Включён' if values['sound'] else 'Выключен',
                'scale': f'{values["scale"]:.0%}',
                'fullscreen': 'Включён' if values['fullscreen'] else 'Выключен',
                'hotkeys': 'Открыть →',
            }
            for index, (caption, key) in enumerate(setting_rows):
                rect = pg.Rect(306, 196 + index * 46, 600, 40)
                active = index == settings_index
                rounded(pg, screen, rect,
                        COLORS['accent'] if active else COLORS['background_alt'], 8)
                text(caption, rect.x + 14, rect.y + 9,
                     COLORS['white'] if active else COLORS['text'], typeface)
                text(shown_values[key], rect.x + 390, rect.y + 10,
                     COLORS['white'] if active else COLORS['accent_alt'], small)
        elif mode == 'hotkeys':
            text('Горячие клавиши', 306, 126, COLORS['text'], heading)
            shortcuts = (
                ('F1', 'этот экран'), ('F11', 'полноэкранный режим'),
                ('Ctrl + / Ctrl −', 'масштаб окна'), ('↑ ↓ ← →', 'навигация'),
                ('Enter', 'открыть или подтвердить'), ('Esc', 'назад / выход'),
                ('B / S', 'купить / продать'), ('F9', 'оценка бумаги'),
                ('F4', 'учебные цели'), ('R / F2', 'повтор / итоговый отчёт'),
                ('+ / −', 'скорость локальной сессии'),
            )
            for index, (keys, action) in enumerate(shortcuts):
                y = 176 + index * 34
                text(keys, 316, y, COLORS['accent_alt'], small)
                text(action, 510, y, COLORS['text'], small)
        rounded(pg, screen, pg.Rect(24, 562, 912, 24), COLORS['panel'], 8)
        footer = ('↑ ↓ разделы    Enter / → открыть    Esc выход' if mode == 'main' else
                  '↑ ↓ выбрать    Enter / → открыть    Esc / ← назад' if mode in ('items', 'action', 'toc', 'settings') else
                  'Esc / ← — вернуться на предыдущий экран' if mode == 'hotkeys' else
                  '↑ ↓ прокрутка    PgUp/PgDn страница    Esc / ← назад')
        text(footer + '    мышь поддерживается', 38, 566, COLORS['muted'], small)
        tooltip = None
        if mouse and mode != 'main' and back_button.collidepoint(mouse):
            tooltip = 'Вернуться на предыдущий экран'
        elif mouse and mode in ('main', 'items') and open_button.collidepoint(mouse):
            tooltip = 'Открыть выбранный пункт'
        elif mouse and mode == 'settings':
            hints = ('Переключить светлое и тёмное оформление',
                     'Изменить размер текста во всех экранах',
                     'Включить или отключить звуки событий',
                     'Изменить размер окна', 'Переключить полноэкранный режим',
                     'Показать все основные сочетания клавиш')
            for index, hint in enumerate(hints):
                if pg.Rect(306, 196 + index * 46, 600, 40).collidepoint(mouse):
                    tooltip = hint
                    break
        draw_tooltip(pg, screen, small, tooltip, mouse)
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
