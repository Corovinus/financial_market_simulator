"""FAST research build: DOS-like menu/manual browser and teaching modules."""
import argparse
import json
from pathlib import Path

from market.levels import CUSTOM_LEVELS
from modules.display import cp866_bytes, open_scaled_display, present_scaled

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
    glyphs = []

    def reset_display():
        nonlocal screen, window, glyphs
        pg.init()
        screen, window = open_scaled_display(pg, (720, 400), args.scale,
                                              'FAST — исследовательская версия')
        font = (ROOT / 'data/fonts/keyrus_8x16.bin').read_bytes()
        if len(font) != 4096:
            raise ValueError('Неверный размер оригинального шрифта')
        glyphs = []
        for code in range(256):
            glyph = pg.Surface((9, 16), pg.SRCALPHA)
            for y, row in enumerate(font[code * 16:(code + 1) * 16]):
                for x in range(8):
                    if row & (0x80 >> x):
                        glyph.set_at((x, y), (255, 255, 255))
                if 0xC0 <= code <= 0xDF and row & 1:
                    glyph.set_at((8, y), (255, 255, 255))
            glyphs.append(glyph)

    reset_display()
    sections = json.loads((ROOT / 'data/converted/manual_sections.json').read_text(encoding='utf-8'))
    grey, blue, green, black = (170, 170, 170), (0, 0, 170), (0, 255, 0), (0, 0, 0)
    group = row = choice = scroll = horizontal = 0
    mode = 'main'
    lines = []
    running = True
    clock = pg.time.Clock()

    def text(value, x, y, color=black):
        for code in cp866_bytes(value):
            glyph = glyphs[code].copy()
            glyph.fill((*color, 255), special_flags=pg.BLEND_RGBA_MULT)
            screen.blit(glyph, (x, y))
            x += 9

    def panel(rect):
        pg.draw.rect(screen, grey, rect)
        pg.draw.rect(screen, black, rect.inflate(-8, -8), 1)

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
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
                    label, prefix = GROUPS[group][1][row]
                    if group == 1 and row == 1:
                        from modules.introduction import run_introduction
                        run_introduction(args.speed, args.scale)
                        reset_display()
                        mode = 'main'
                        continue
                    if mode == 'action' and choice == 1:
                        if label in ('Case B01', 'Case B02'):
                            from modules.bidask import run_session
                            run_session(ROOT / f'data/original/{label[5:]}.PAR', args.speed, args.scale)
                            reset_display()
                            mode = 'main'
                            continue
                        custom = next((level for level in CUSTOM_LEVELS if level.name == label), None)
                        if custom is not None:
                            from modules.bidask import run_session
                            run_session(custom.scenario, args.speed, args.scale)
                            reset_display()
                            mode = 'main'
                            continue
                        from modules.workshops import run_module
                        run_module(label, args.speed, args.scale)
                        reset_display()
                        mode = 'main'
                        continue
                    else:
                        title = next(name for name in sections if name.startswith(prefix))
                        lines = [title, ''] + sections[title].replace('`', '').replace('|', '').splitlines()
                    mode, scroll, horizontal = 'reader', 0, 0

        if not running:
            break
        screen.fill(blue)
        for x in range(0, 720, 3):
            pg.draw.line(screen, grey, (x, 40), (x, 383), 1)
        for y in range(40, 384, 3):
            pg.draw.line(screen, blue, (0, y), (719, y), 1)
        panel(pg.Rect(0, 0, 720, 40))
        x = 8
        for index, (label, _) in enumerate(GROUPS):
            if index == group:
                pg.draw.rect(screen, green, (x - 2, 13, len(label) * 9 + 4, 16))
                pg.draw.rect(screen, black, (x - 2, 13, len(label) * 9 + 4, 16), 1)
            text(label, x, 13)
            x += (len(label) + 1) * 9
        panel(pg.Rect(171, 208, 441, 144))
        for n, value in enumerate(('Лаборатория экспериментальной экономики', '', 'Программа FAST',
                                  'Финансовый анализ и торговля Ценными бумагами', 'Курс заочного обучения', '1994 г.')):
            text(value, 391 - len(value) * 9 // 2, 240 + n * 16 - (16 if n > 1 else 0))
        if mode in ('items', 'action'):
            options = [item[0] for item in GROUPS[group][1]] if mode == 'items' else ['Описание игры', 'Торговая сессия']
            selection = row if mode == 'items' else choice
            panel(pg.Rect(72, 48, 306, 24 + 24 * len(options)))
            for index, value in enumerate(options):
                if index == selection:
                    pg.draw.rect(screen, green, (81, 58 + index * 24, 288, 18))
                    pg.draw.rect(screen, black, (81, 58 + index * 24, 288, 18), 1)
                text(value, 90, 59 + index * 24)
        elif mode == 'reader':
            panel(pg.Rect(9, 43, 702, 335))
            for index, value in enumerate(lines[scroll:scroll + 20]):
                text(value[horizontal:horizontal + 76], 18, 51 + index * 16)
        elif mode == 'exit':
            panel(pg.Rect(153, 160, 414, 80))
            text('Вы завершаете работу?', 189, 176)
            text('Enter/Y — Да   Esc/N — Нет', 171, 208)
        pg.draw.rect(screen, grey, (0, 384, 720, 16))
        text('Esc Назад  Enter Выбор  ↑↓ Прокрутка' if mode == 'reader' else 'Все вкладки доступны; D — текст FAST.DOC', 9, 384)
        present_scaled(pg, screen, window)
        if args.screenshot:
            pg.image.save(window, args.screenshot)
            running = False
        clock.tick(30)
    pg.quit()


if __name__ == '__main__':
    main()
