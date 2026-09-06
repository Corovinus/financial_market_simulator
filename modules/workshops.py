"""Interactive DOS-like lessons for every FAST item outside BIDASK B01/B02."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .educational import (
    binomial_option,
    black_scholes,
    capm_statistics,
    information_expected_value,
    immunization_ratio,
    macaulay_duration,
    option_payoff,
    risk_premium_bound,
)
from .display import open_scaled_display, present_scaled
from .theme import COLORS, card, font, label as draw_label, mouse_position, rounded


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Field:
    name: str
    value: float
    minimum: float
    maximum: float
    step: float
    integer: bool = False

    def display(self) -> str:
        if self.integer:
            return str(int(self.value))
        return f"{self.value:.2f}"


def _spec(label: str) -> tuple[str, str, list[Field]]:
    """Return title, short purpose and documented starting parameters."""
    if label == "Case B03":
        return ("B03 — Облигации и фьючерсы", "Дисконтирование семи рынков и расчёт форвардов",
                [Field("Ставка, %", 4, 0, 100, 1), Field("Деньги", 1000, -9999, 99999, 100)])
    if label == "Case B04":
        return ("B04 — Неопределённая ставка", "Сравнение дюрации активов и обязательств",
                [Field("Ставка, %", 15, 0, 100, 1), Field("Активы", 1000, 0, 99999, 50),
                 Field("Обязательства", 900, 0, 99999, 50)])
    if label in ("Case CA1", "Case CA2", "Case CA3"):
        risk = 1 if label != "Case CA3" else 0
        return (f"{label} — Рынок акций", "Ожидаемый капитал и премиальная лотерея",
                [Field("Капитал C", 2500, 0, 10000, 100),
                 Field("Тип инвестора", 1 if risk else 4, 1, 4, 1, True)])
    if label == "Портфель акций":
        return ("TutCA — Портфель акций", "Рыночный портфель, beta и цена риска", [
            Field("Безрисковая ставка, %", 4, -20, 100, 1)])
    if label in ("Case OP1", "Case OP2", "Case OP3"):
        defaults = {"Case OP1": (20, 25, 240, 1), "Case OP2": (20, 25, 240, 2),
                    "Case OP3": (400, 410, 30, 3)}
        spot, strike, volatility, periods = defaults[label]
        return (f"{label} — Опционы", "Европейская цена и конечные выплаты",
                [Field("Акция S", spot, 1, 999, 1), Field("Страйк K", strike, 1, 999, 1),
                 Field("Волатильность, %", volatility, 1, 1000, 10), Field("Ставка, %", 12, -20, 100, 1),
                 Field("Периоды", periods, 1, 12, 1, True)])
    if label == "Опционы":
        return ("TutOP — Опционные стратегии", "Сравнение call, put и защитной позиции",
                [Field("Акция S", 20, 1, 999, 1), Field("Страйк K", 25, 1, 999, 1),
                 Field("Волатильность, %", 240, 1, 1000, 10)])
    if label in ("Case RE1", "Case RE2", "Case RE3"):
        return (f"{label} — Эффективность", "Ожидаемая оценка по раскрытым состояниям",
                [Field("Деньги", 1000, -9999, 99999, 100), Field("Акции ABC", 10, -100, 100, 1, True),
                 Field("Акции CRA", 10, -100, 100, 1, True)])
    if label == "Дюрация":
        return ("TutBO — Дюрация", "Текущая стоимость, дюрация и иммунитет",
                [Field("Ставка, %", 10, -20, 100, 1), Field("Актив", 1000, 1, 99999, 50),
                 Field("Обязательство", 850, 1, 99999, 50)])
    raise KeyError(label)


def _calculate(label: str, fields: list[Field]) -> list[str]:
    values = [field.value for field in fields]
    if label == "Case B03":
        rate, cash = values
        coupon, duration = macaulay_duration((10, 10, 110), rate)
        zero1 = 100 / (1 + rate / 100)
        zero2 = 100 / (1 + rate / 100) ** 2
        zero3 = 100 / (1 + rate / 100) ** 3
        return [f"Наличные в конце года: {cash * (1 + rate / 100):.2f}",
                f"Купонная облигация: {coupon:.2f}  D={duration:.2f}",
                f"Нулевые облигации: {zero1:.2f} / {zero2:.2f} / {zero3:.2f}",
                "Фьючерс 1: поставка бумаги 3 в начале года 2",
                "Фьючерс 2: поставка бумаги 4 в начале года 3"]
    if label == "Case B04":
        rate, assets, liabilities = values
        asset_one, asset_two = macaulay_duration((0, 160, 200, 250), rate)
        asset_two_value, _ = macaulay_duration((30, 100, 47, 0), rate)
        liability_two = 100 / (1 + rate / 100) ** 2
        liability_three = 100 / (1 + rate / 100) ** 3
        asset_value = assets / 1000 * (asset_one + asset_two_value)
        liability_value = liabilities / 1000 * (liability_two + liability_three)
        return [f"PV актива A: {asset_one:.2f}; PV B: {asset_two_value:.2f}",
                f"PV активов (масштаб): {asset_value:.2f}",
                f"PV обязательств: {liability_value:.2f}",
                f"Запас/дефицит: {asset_value - liability_value:.2f}",
                "Потоки A=(0,160,200,250), B=(30,100,47,0)"]
    if label in ("Case CA1", "Case CA2", "Case CA3"):
        capital, investor = values
        bound = risk_premium_bound(capital, label != "Case CA3", int(investor))
        prices = (316, 24, 52) if investor == 1 else (78, 100, 52) if investor == 2 else (78, 24, 210) if investor == 3 else (0, 0, 0)
        terminal = ((5, 5, 5, 24, 25, 30, 32, 68, 75, 75),
                    (4, 5, 10, 21, 66, 65, 65, 20, 20, 20),
                    (55, 55, 49, 22, 22, 20, 10, 10, 10, 10))
        average_liquidation = sum(prices[index] * sum(terminal[index]) / 10
                                  for index in range(3))
        fixed = "Фиксированные цены 28/26/25" if label == "Case CA2" else "Двойной аукцион"
        return [f"Начальная структура: {prices[0]}/{prices[1]}/{prices[2]}",
                f"Средняя ликвидация акций: {average_liquidation:.2f}",
                f"Премиальная граница C={capital:.0f}: {bound}",
                fixed, "25 лотерей × $0.20; максимум $5"]
    if label == "Портфель акций":
        result = capm_statistics(((.10, .06, .14), (.02, .04, .01),
                                  (.18, .12, .20), (-.04, .02, -.02)),
                                 risk_free=values[0] / 100.0)
        return [f"Рынок: {result['market'] * 100:.2f}%",
                "Ожидание: " + " / ".join(f"{x * 100:.2f}%" for x in result["expected"]),
                "Beta: " + " / ".join(f"{x:.3f}" for x in result["beta"]),
                f"Премия за риск: {result['risk_premium'] * 100:.2f}%"]
    if label in ("Case OP1", "Case OP2", "Case OP3", "Опционы"):
        spot, strike, volatility = values[:3]
        periods = int(values[4]) if len(values) > 4 else 1
        rate = values[3] if len(values) > 3 else 12
        call = binomial_option(spot, strike, rate, volatility, periods, "call")
        put = binomial_option(spot, strike, rate, volatility, periods, "put")
        up = spot * math.exp(volatility / 100 / math.sqrt(periods))
        down = spot / math.exp(volatility / 100 / math.sqrt(periods))
        return [f"Call (биномиальная): {call:.4f}", f"Put (биномиальная): {put:.4f}",
                f"Состояния акции: вверх {up:.2f}; вниз {down:.2f}",
                f"Payoff call/put при S: {option_payoff(spot, strike, 'call'):.2f} / {option_payoff(spot, strike, 'put'):.2f}",
                f"Black-Scholes call: {black_scholes(spot, strike, rate, volatility, 1 / periods):.4f}"]
    if label in ("Case RE1", "Case RE2", "Case RE3"):
        cash, abc, cra = values
        matrix = (((0, 8), (12, 12), (24, 18)) if label == "Case RE1" else
                  ((0, 8), (12, 8), (24, 18)) if label == "Case RE2" else
                  ((0, 0), (20, 25), (40, 60)))
        expected = information_expected_value(matrix)
        capital = cash + abc * expected / 10 + cra * expected / 10
        return [f"Средняя цена ABC/CRA: {expected:.2f}", f"Ожидаемый капитал: {capital:.2f}",
                "Информация Not z/Not y исключает состояния", "Ставка и кредит: 0%"]
    if label == "Дюрация":
        rate, assets, liability = values
        pv, duration = macaulay_duration((0, 160, 200, 250), rate)
        liability_two, liability_duration = macaulay_duration((0, liability, 0, 0), rate)
        liability_three, duration_three = macaulay_duration((0, 0, liability, 0), rate)
        ratio = immunization_ratio(duration, liability_duration)
        return [f"PV актива A: {pv:.2f}; D={duration:.3f}",
                f"PV долга (год 2): {liability_two:.2f}; D={liability_duration:.3f}",
                f"PV долга (год 3): {liability_three:.2f}; D={duration_three:.3f}",
                f"Доля актива для иммунитета: {ratio:.3f}",
                f"Свободные деньги после покупки: {assets - ratio * liability_two:.2f}"]
    return []


def _font(pg, path: Path):
    data = path.read_bytes()
    if len(data) != 4096:
        raise ValueError("Неверный размер оригинального шрифта")
    glyphs = []
    for code in range(256):
        glyph = pg.Surface((9, 16), pg.SRCALPHA)
        for y, row in enumerate(data[code * 16:(code + 1) * 16]):
            for x in range(8):
                if row & (0x80 >> x):
                    glyph.set_at((x, y), (255, 255, 255))
            if 0xC0 <= code <= 0xDF and row & 1:
                glyph.set_at((8, y), (255, 255, 255))
        glyphs.append(glyph)
    return glyphs


def run_module(label: str, speed: float = 1.0, scale: float = 1.0):
    """Run one of the recovered teaching tabs and return its last result."""
    title, purpose, fields = _spec(label)
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError("Скорость должна быть положительной")
    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale, "FAST — " + label)
    body_font = font(pg, 17)
    small_font = font(pg, 14)
    title_font = font(pg, 27, bold=True)
    manual = []
    manual_path = ROOT / "data/converted/manual_sections.json"
    if manual_path.exists():
        sections = json.loads(manual_path.read_text(encoding="utf-8"))
        prefixes = {
            "Портфель акций": "Описание TutCAPM",
            "Опционы": "Описание TutOP",
            "Дюрация": "Описание TutBO",
            "Case B03": "Описание B03",
            "Case B04": "Описание B04",
            "Case CA1": "Описание CA1",
            "Case CA2": "Описание CA2",
            "Case CA3": "Описание CA3",
            "Case OP1": "Описание OP1",
            "Case OP2": "Описание OP2",
            "Case OP3": "Описание OP3",
            "Case RE1": "Описание RE1",
            "Case RE2": "Описание RE2",
            "Case RE3": "Описание RE3",
        }
        prefix = prefixes.get(label, "Описание " + label)
        key = next((name for name in sections if name.startswith(prefix)), None)
        if key:
            manual = sections[key].replace("`", "").replace("|", "").splitlines()
    selected, input_text, mode, scroll, frame = 0, "", "calc", 0, 1
    status, status_until = "", 0.0
    running, last = True, _calculate(label, fields)
    clock = pg.time.Clock()

    def write(value, x, y, color=None, face=None):
        draw_label(pg, screen, face or body_font, value, (x, y), color or COLORS['text'])

    def draw():
        screen.fill(COLORS['background'])
        pg.draw.circle(screen, (22, 58, 92), (920, 0), 250)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        frame_text = ""
        if label == "Опционы":
            frame_text = f"  Кадр {frame}: " + ("Сравнение портфелей" if frame == 1 else
                         "Опционные стратегии" if frame == 2 else "Желаемый график")
        elif label == "Портфель акций":
            frame_text = f"  Кадр {frame}/6"
        write(title + frame_text, 48, 30, COLORS['accent'], title_font)
        write(purpose, 50, 86, COLORS['muted'], small_font)
        if mode == "manual":
            card(pg, screen, pg.Rect(36, 116, 888, 420), COLORS['panel'], COLORS['border'])
            for index, line in enumerate(manual[scroll:scroll + 24]):
                write(line[:104], 58, 134 + index * 16, COLORS['text'], small_font)
            footer = "↑↓/PgUp/PgDn текст   Esc расчёт   Q выход"
        else:
            card(pg, screen, pg.Rect(36, 116, 410, 350), COLORS['panel'], COLORS['border'])
            card(pg, screen, pg.Rect(468, 116, 456, 220), COLORS['panel'], COLORS['border'])
            write('Параметры', 60, 140, COLORS['text'], body_font)
            for index, field in enumerate(fields):
                y = 184 + index * 43
                field_rect = pg.Rect(58, y - 5, 366, 34)
                rounded(pg, screen, field_rect, COLORS['accent'] if index == selected else COLORS['background_alt'], 8)
                rounded(pg, screen, field_rect, COLORS['accent_alt'] if index == selected else COLORS['border'], 8, 2 if index == selected else 1)
                write(field.name, 72, y + 3, COLORS['white'], body_font)
                write(field.display(), 320, y + 3, COLORS['accent_alt'], body_font)
            write("РЕЗУЛЬТАТЫ", 494, 140, COLORS['text'], body_font)
            for index, line in enumerate(last[:14]):
                write(line[:52], 494, 178 + index * 24, COLORS['text'], small_font)
            if label == "Опционы":
                footer = "F1-F3 кадр  F9 пример  ↑↓ поле  ←→ изменить  Enter ввод  D текст  F10 сброс  Q выход"
            elif label == "Портфель акций":
                footer = "F1-F6 кадр  ↑↓ поле  ←→ изменить  Enter ввод  D текст  F10 сброс  Q выход"
            else:
                footer = "↑↓ поле  ←→ изменить  Enter ввод  D текст  F10 сброс  Esc выход"
            if label in ("Case OP1", "Case OP2", "Case OP3", "Опционы"):
                card(pg, screen, pg.Rect(468, 354, 456, 112), COLORS['panel'], COLORS['border'])
                write("График payoff", 492, 370, COLORS['text'], small_font)
                pg.draw.line(screen, COLORS['border'], (510, 444), (888, 444), 1)
                pg.draw.line(screen, COLORS['border'], (510, 390), (510, 452), 1)
                strike = fields[1].value
                maximum = max(fields[0].value * 2, strike * 2, 1)
                points_call, points_put = [], []
                for index in range(33):
                    spot = maximum * index / 32
                    x = 510 + index * 12
                    points_call.append((x, 444 - min(50, option_payoff(spot, strike, "call") * 2)))
                    points_put.append((x, 444 - min(50, option_payoff(spot, strike, "put") * 2)))
                pg.draw.lines(screen, COLORS['buy'], False, points_call, 2)
                pg.draw.lines(screen, COLORS['warning'], False, points_put, 2)
            elif label in ("Дюрация", "Case B04"):
                card(pg, screen, pg.Rect(468, 354, 456, 112), COLORS['panel'], COLORS['border'])
                write("График стоимость/ставка", 492, 370, COLORS['text'], small_font)
                pg.draw.line(screen, COLORS['border'], (510, 444), (888, 444), 1)
                pg.draw.line(screen, COLORS['border'], (510, 390), (510, 452), 1)
                bars = [max(0.0, min(1.0, abs(float(value)) / 2000.0))
                        for value in (fields[1].value, fields[-1].value)]
                for index, height in enumerate(bars):
                    pg.draw.rect(screen, COLORS['buy'] if index == 0 else COLORS['warning'],
                                 (580 + index * 120, 444 - int(height * 55), 62, int(height * 55)), border_radius=5)
        rounded(pg, screen, pg.Rect(36, 548, 888, 34), COLORS['panel'], 8)
        write(footer, 52, 556, COLORS['muted'], small_font)
        if input_text:
            rounded(pg, screen, pg.Rect(36, 492, 888, 42), COLORS['panel_alt'], 8)
            rounded(pg, screen, pg.Rect(36, 492, 888, 42), COLORS['accent'], 1, 2)
        if status and time.monotonic() < status_until and not input_text:
            rounded(pg, screen, pg.Rect(36, 492, 888, 42), COLORS['panel_alt'], 8)
            rounded(pg, screen, pg.Rect(36, 492, 888, 42), COLORS['warning'], 1, 2)
            write(status[:100], 52, 503, COLORS['warning'], small_font)

    def message(value, seconds=3.0):
        nonlocal status, status_until
        status, status_until = value, time.monotonic() + seconds

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                position = mouse_position(pg, event, window, screen)
                if position and mode != "manual" and 50 <= position[0] <= 430 and 175 <= position[1] <= 466:
                    selected = max(0, min(len(fields) - 1, (position[1] - 175) // 43))
                continue
            elif event.type == pg.KEYDOWN:
                key = event.key
                if key in (pg.K_ESCAPE, pg.K_q):
                    if mode == "manual":
                        mode = "calc"
                    else:
                        running = False
                elif mode == "manual":
                    if key in (pg.K_DOWN, pg.K_PAGEDOWN):
                        scroll = min(max(0, len(manual) - 24), scroll + (10 if key == pg.K_PAGEDOWN else 1))
                    elif key in (pg.K_UP, pg.K_PAGEUP):
                        scroll = max(0, scroll - (10 if key == pg.K_PAGEUP else 1))
                    elif key == pg.K_HOME:
                        scroll = 0
                elif key == pg.K_d:
                    mode = "manual" if manual else "calc"
                    scroll = 0
                    message("Открыт текст FAST.DOC" if mode == "manual" else "Возврат к расчётам")
                elif label == "Опционы" and key in (pg.K_F1, pg.K_F2, pg.K_F3):
                    frame = key - pg.K_F1 + 1
                elif label == "Портфель акций" and pg.K_F1 <= key <= pg.K_F6:
                    frame = key - pg.K_F1 + 1
                elif label == "Опционы" and key == pg.K_F9:
                    # FAST's first frame offers standard portfolios.  The
                    # compact port here uses its canonical long-straddle
                    # example (K=50) as a reproducible preset.
                    fields[1].value = 50
                    last = _calculate(label, fields)
                    message("F9 — установлен учебный пример")
                elif key == pg.K_F10:
                    _, _, fields = _spec(label)
                    selected, input_text = 0, ""
                    last = _calculate(label, fields)
                    message("Параметры восстановлены")
                elif input_text:
                    if key == pg.K_BACKSPACE:
                        input_text = input_text[:-1]
                    elif key == pg.K_RETURN:
                        try:
                            value = float(input_text)
                            field = fields[selected]
                            if not field.minimum <= value <= field.maximum:
                                raise ValueError("Значение вне диапазона")
                            field.value = int(value) if field.integer else value
                            last = _calculate(label, fields)
                            message("Параметр обновлён")
                        except ValueError as error:
                            message(str(error) or "Неверное значение")
                        input_text = ""
                    elif event.unicode and event.unicode in "0123456789.-":
                        input_text += event.unicode
                elif key in (pg.K_UP, pg.K_DOWN):
                    selected = (selected + (1 if key == pg.K_DOWN else -1)) % len(fields)
                elif key in (pg.K_LEFT, pg.K_RIGHT):
                    field = fields[selected]
                    field.value = min(field.maximum, max(field.minimum,
                                      field.value + (field.step if key == pg.K_RIGHT else -field.step)))
                    last = _calculate(label, fields)
                elif key == pg.K_RETURN:
                    input_text = ""
                elif event.unicode and event.unicode in "0123456789.-":
                    input_text = event.unicode
        draw()
        if input_text:
            write("Ввод: " + input_text + "_", 52, 503, COLORS['text'], body_font)
        present_scaled(pg, screen, window)
        clock.tick(max(1, int(30 * max(0.1, min(float(speed), 10.0)))))
    pg.quit()
    return last
