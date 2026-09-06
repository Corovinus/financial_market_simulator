"""Guided port of DEMO.EXE FTS_TUT.SLD used by the Торги/Знакомство tab."""
from __future__ import annotations

import time
from pathlib import Path

from market.orderbook import OrderBook, OrderError
from .bidask import _font
from .display import open_scaled_display, present_scaled
from .theme import COLORS, card, font, label, mouse_position, rounded

ROOT = Path(__file__).resolve().parents[1]
SLD_SOURCE = ROOT / "data" / "converted" / "FTS_TUT.SLD.strings.txt"
CPBND, ZCP = 0, 1


def _book(*quotes):
    book = OrderBook(2, ranked_queue=True)
    for owner, instrument, side, price, quantity in quotes:
        book.submit(owner, instrument, side, price, quantity)
    return book


def _initial_book():
    return _book((2, CPBND, "ask", 115, 5),
                 (3, ZCP, "bid", 32, 99),
                 (4, ZCP, "ask", 88, 99))


# Captions recovered from FTS_TUT.SLD. Decorative slide drawings are replaced
# with the same DOS colours and the same required actions.
SCENES = (
    ("ФИНАНСОВЫЙ АНАЛИЗ и ТОРГОВЛЯ ЦЕННЫМИ БУМАГАМИ",
     ("Дополнительный учебный материал", "Финансовая Торговая Система - Обучающая программа",
      "Нажмите любую клавишу..."), "pause"),
    ("ФИНАНСОВАЯ ТОРГОВАЯ СИСТЕМА",
     ("Данная программа научит Вас работать на электронном рынке.",
      "Вы научитесь выставлять предложения на покупку и продажу.",
      "Вы научитесь покупать и продавать ценные бумаги.",
      "В программе несколько рынков, в этом примере показаны два.",
      "Чтобы перейти к следующему экрану, нужно выполнить все инструкции.",
      "Клавиша F1 выводит дополнительную помощь. Нажмите F1."), "f1"),
    ("Помощь по управлению",
     ("F1 - данный текст", "PgUp - следующий экран", "PgDn - предыдущий экран",
      "Home - первый экран", "F10, Esc - выход"), "pause"),
    ("Ввод заявки",
     ("Стрелками выберите нужную позицию.", "Точка разделяет цену и количество.",
      "Backspace удаляет последний символ.", "Esc отменяет ввод, Enter отправляет заявку.",
      "Цена: от 1 до 999; количество: от 1 до 99."), "pause"),
    ("Выбор меню",
     ("Стрелки, Tab и Shift-Tab выбирают пункт.", "Enter подтверждает выбор.",
      "F10 или Esc завершает работу."), "pause"),
    ("Сделка",
     ("B - купить по текущему продавцу в Ask.", "S - продать текущему покупателю в Bid.",
      "Backspace и Esc отменяют ввод, Enter подтверждает."), "pause"),
    ("Знакомство с рынком",
     ("Так выглядит рабочий экран Финансовой Торговой Системы.",
      "Слева показаны заявки Bid, справа - заявки Ask.",
      "Внизу отображаются деньги, бумаги, время и номер периода."), "market"),
    ("Ваш участник",
     ("ID:  1 - это Ваш номер участника.", "Красная рамка показывает текущую позицию.",
      "Перейдите стрелками к таблице и нажмите Enter."), "select"),
    ("Формат заявки",
     ("Каждая заявка состоит из двух чисел, разделенных точкой.",
      "Слева от точки указана цена, а справа - количество.",
      "Цена и количество могут быть только целыми.",
      "Цена - от 1 до 999, количество - от 1 до 99.",
      "Теперь выставим первую заявку на покупку."), "pause"),
    ("Первая заявка",
     ("Введите заявку на покупку 10 штук CpBnd по цене 50 за штуку.",
      "Сначала вводится ЦЕНА, затем точка, затем КОЛИЧЕСТВО.",
      "Наберите на клавиатуре \"50.10\" и нажмите Enter."), "quote"),
    ("Заявка принята",
     ("Заявка принята и стала текущей заявкой Bid.",
      "Чужие заявки показаны желтым цветом, Ваша - зеленым.",
      "Текущая цена Bid улучшается только более высокой заявкой."), "pause"),
    ("Конкуренция покупателей",
     ("Выберите позицию Bid рынка ZCp. Текущая цена 32.",
      "Установите заявку на покупку по цене 33.",
      "Наберите \"33.1\" и нажмите Enter."), "quote"),
    ("Очередь заявок",
     ("Новая заявка с более высокой ценой вытеснила прежнюю.",
      "Прежняя заявка сохранена в очереди рынка.",
      "Количество заявки не влияет на то, какая цена главная."), "pause"),
    ("Нарушение правила рынка",
     ("Попробуйте улучшить Bid CpBnd. Текущая цена равна 55.",
      "Наберите \"54.99\" и нажмите Enter.",
      "Цена 54 ниже текущей и не может стать лучшей."), "invalid_quote"),
    ("Правило Bid и Ask",
     ("Market rule violation", "Покупатель повышает Bid, продавец понижает Ask.",
      "Если в Ask нет заявки, продавец может начать с любой цены."), "pause"),
    ("Заявка на продажу",
     ("Введите заявку на продажу 5 бумаг CpBnd по цене 123.",
      "Выберите Ask, наберите \"123.5\" и нажмите Enter."), "quote"),
    ("Покупка по рынку",
     ("На Ask рынка ZCp стоит заявка 54.50.",
      "Нажмите B, введите количество 8 и нажмите Enter."), "buy8"),
    ("Результат покупки",
     ("Сделка совершена по цене 54.", "Ask уменьшился с 50 до 42.",
      "Cash: 4238 - 8 * 54 = 3806.", "Ваши бумаги ZCp: 12 + 8 = 20."), "pause"),
    ("Полное исполнение заявки",
     ("Нажмите B еще раз и купите оставшиеся 42 бумаги.",
      "Введите количество 42 и подтвердите Enter."), "buy42"),
    ("Ask исчезает",
     ("Вторая сделка полностью исполнила заявку продавца.",
      "Заявка 54.50 исчезла с экрана. Ваше количество ZCp равно 62."), "pause"),
    ("Как работает очередь",
     ("Вытесненные заявки хранятся в очереди.",
      "Когда текущая заявка полностью потреблена, последняя вытесненная",
      "заявка возвращается на экран. Очередь может быть пустой."), "pause"),
    ("Продажа бумаг",
     ("На Bid CpBnd появилась заявка 123.99.",
      "Нажмите S, продайте 5 бумаг, введите 5 и нажмите Enter."), "sell5"),
    ("Результат продажи",
     ("Сделка совершена по цене 123.", "Cash: 1538 + 5 * 123 = 2153.",
      "Количество CpBnd уменьшилось с 5 до 0."), "pause"),
    ("Короткая позиция",
     ("Нажмите S и продайте еще 90 бумаг.",
      "Продажа разрешена и без бумаг. Введите 90 и подтвердите Enter."), "sell90"),
    ("Продажа без покрытия",
     ("Количество CpBnd стало -90: это короткая позиция.",
      "Cash: 2153 + 90 * 123 = 13223.",
      "Короткая позиция учитывается при расчетах периода."), "pause"),
    ("Недопустимое количество",
     ("Попробуйте продать еще 3 бумаги.",
      "Нажмите S, введите 3 и подтвердите Enter.",
      "Другой трейдер мог забрать Bid, пока Вы вводили заявку."), "invalid_qty"),
    ("Отмена заявки",
     ("Invalid quantity", "Количество больше доступной заявки, поэтому сделка отменена.",
      "Нажмите Esc, чтобы отменить ввод и продолжить урок."), "cancel"),
    ("Период и попытка",
     ("Период - отрезок времени, в котором идут торги.",
      "Попытка (Trial) начинается с новой торговой сессии.",
      "Номер периода и попытки виден на рабочем экране."), "pause"),
    ("Время и последняя сделка",
     ("Time remaining показывает оставшееся время торгов.",
      "Last - цена последней сделки. Int - процент по денежной позиции."), "pause"),
    ("Расчет в конце периода",
     ("Сначала начисляются проценты по Cash.", "Отрицательный Cash приносит убыток.",
      "Затем рассчитываются платежи по бумагам; по короткой позиции платеж вычитается."),
     "pause"),
    ("Расчет деривативов",
     ("После бумаг рассчитываются производные инструменты.",
      "Когда расчеты завершены, рынок будет открыт снова.", "Market will reopen shortly."),
     "pause"),
    ("Очки и приз",
     ("Cash Prize показывает приз за текущую попытку.",
      "Cumulative Earnings - накопленный результат.",
      "После завершения периода начинается следующий период."), "pause"),
    ("Урок завершен",
     ("Теперь Вы умеете выставлять заявки и ждать улучшения цены.",
      "Можно отправлять заявку и ждать ее исполнения.",
      "Можно явно совершать сделку клавишами B и S.",
      "Нажмите любую клавишу, чтобы выйти в меню FAST."), "finish"),
)


def _quote(value):
    if value.count(".") != 1:
        raise ValueError
    price_text, quantity_text = value.split(".")
    if not price_text or not quantity_text:
        raise ValueError
    price, quantity = int(price_text), int(quantity_text)
    if not 1 <= price <= 999 or not 1 <= quantity <= 99:
        raise ValueError
    return price, quantity


def _quantity(value):
    if not value or not value.isdigit():
        raise ValueError
    result = int(value)
    if not 1 <= result <= 99:
        raise ValueError
    return result


def run_introduction(speed: float = 1.0, scale: float = 1.0,
                     close_display: bool = True):
    """Run the guided lesson; F10/Esc opens the DOS-style exit confirmation."""
    if not isinstance(speed, (int, float)) or speed <= 0:
        raise ValueError("Скорость должна быть положительной")
    import pygame as pg

    pg.init()
    screen, window = open_scaled_display(pg, (960, 600), scale, "FAST — DEMO.EXE FTS_TUT")
    body_font = font(pg, 18)
    small_font = font(pg, 15)
    title_font = font(pg, 28, bold=True)
    C = {"blue": COLORS["background"], "white": COLORS["text"], "black": COLORS["black"],
         "yellow": COLORS["warning"], "green": COLORS["buy"], "cyan": COLORS["accent"],
         "red": COLORS["danger"], "grey": COLORS["panel"], "brown": COLORS["panel_alt"]}
    page, text, mode, side_choice = 0, "", "", "bid"
    moved, confirm, help_visible, running = False, False, False, True
    cash, holdings = 4238, [5, 12]
    book = _initial_book()
    status, status_until = "", 0.0
    clock = pg.time.Clock()

    def write(value, x, y, color="white", face=None):
        rgb = (C.get(color) or COLORS.get(color) or COLORS["text"]) if isinstance(color, str) else color
        label(pg, screen, face or body_font, value, (x, y), rgb)

    def wrapped(value, x, y, color="black"):
        words, line, row = str(value).split(), "", 0
        for word in words:
            if line and len(line) + len(word) + 1 > 68:
                write(line, x, y + row * 18, color)
                line, row = word, row + 1
            else:
                line = word if not line else line + " " + word
        if line:
            write(line, x, y + row * 18, color)

    def set_status(value):
        nonlocal status, status_until
        status, status_until = value, time.monotonic() + 3

    def reset(new_page):
        nonlocal book, text, mode, moved, side_choice, help_visible, cash
        text, mode, moved, side_choice, help_visible = "", "", False, "bid", False
        if new_page == 0:
            book = _initial_book()
            cash = 4238
            holdings[:] = [5, 12]
        elif new_page == 11:
            book = _book((2, CPBND, "ask", 115, 5), (3, ZCP, "bid", 32, 99),
                         (4, ZCP, "ask", 88, 99))
        elif new_page == 13:
            book = _book((3, CPBND, "bid", 55, 9), (4, CPBND, "ask", 125, 5),
                         (3, ZCP, "bid", 33, 1), (4, ZCP, "ask", 253, 9))
        elif new_page == 15:
            book = _book((3, CPBND, "bid", 54, 9), (4, CPBND, "ask", 125, 99),
                         (3, ZCP, "bid", 33, 1), (4, ZCP, "ask", 253, 9))
        elif new_page == 16:
            book = _book((3, CPBND, "bid", 54, 9), (3, ZCP, "bid", 33, 1),
                         (4, ZCP, "ask", 54, 50))
        elif new_page == 21:
            book = _book((3, CPBND, "bid", 123, 99), (3, ZCP, "bid", 33, 1),
                         (4, ZCP, "ask", 253, 9))

    def advance():
        nonlocal page
        page = min(len(SCENES) - 1, page + 1)
        reset(page)

    def quote_text(value):
        return "нет" if value is None else "{}.{}".format(value.price, value.quantity)

    def market():
        card(pg, screen, pg.Rect(36, 105, 888, 270), COLORS['panel'], COLORS['border'])
        write("Time remaining    298", 60, 128, "muted", small_font); write("ID:  1", 810, 128, "white", small_font)
        write("Bid", 280, 164, "buy", small_font); write("Ask", 470, 164, "sell", small_font); write("Units", 690, 164, "muted", small_font)
        for row, instrument in enumerate((CPBND, ZCP)):
            y = 204 + row * 70
            write("CpBnd" if instrument == CPBND else "ZCp", 60, y + 9, "white")
            bid, ask = book.best(instrument, "bid"), book.best(instrument, "ask")
            bid_field = pg.Rect(230, y - 7, 160, 42)
            ask_field = pg.Rect(420, y - 7, 160, 42)
            quote_page = SCENES[page][2] in ("quote", "invalid_quote")
            bid_active = page == 7 or quote_page and side_choice == "bid"
            ask_active = page == 7 or quote_page and side_choice == "ask"
            rounded(pg, screen, bid_field, COLORS['background_alt'], 8)
            rounded(pg, screen, bid_field, COLORS['accent'] if bid_active else COLORS['border'], 8, 2 if bid_active else 1)
            rounded(pg, screen, ask_field, COLORS['background_alt'], 8)
            rounded(pg, screen, ask_field, COLORS['accent'] if ask_active else COLORS['border'], 8, 2 if ask_active else 1)
            write(quote_text(bid), 248, y + 2, "buy" if bid and bid.owner == 0 else "yellow")
            write(quote_text(ask), 438, y + 2, "sell" if ask and ask.owner == 0 else "yellow")
            write(str(holdings[instrument]), 700, y + 2, "white")
        write("Cash", 60, 340, "muted", small_font); write(str(cash), 125, 336, "white")
        write("Int", 250, 340, "muted", small_font); write("25.00", 295, 336, "white")
        write("Period 1", 440, 340, "muted", small_font); write("Trial 1", 565, 336, "white")
        write("Last  0", 720, 340, "muted", small_font)

    def draw():
        screen.fill(C["blue"])
        pg.draw.circle(screen, (22, 58, 92), (920, 0), 250)
        rounded(pg, screen, pg.Rect(24, 18, 912, 58), COLORS['panel'], 15)
        write("ФИНАНСОВАЯ ТОРГОВАЯ СИСТЕМА", 48, 30, "cyan", title_font)
        write(f"Урок {page + 1} / {len(SCENES)}", 800, 36, "muted", small_font)
        title, lines, kind = SCENES[page]
        market_kinds = ("market", "select", "quote", "invalid_quote", "buy8",
                        "buy42", "sell5", "sell90", "invalid_qty", "cancel")
        if kind in market_kinds:
            market(); card(pg, screen, pg.Rect(36, 398, 888, 110), COLORS['panel'], COLORS['border'])
            write(title, 60, 416, "yellow", body_font)
            for row, line in enumerate(lines):
                wrapped(line, 60, 450 + row * 18, "white")
            if kind in ("quote", "invalid_quote"):
                rounded(pg, screen, pg.Rect(36, 518, 888, 42), COLORS['panel_alt'], 8)
                write(("Bid" if side_choice == "bid" else "Ask") + " заявка: " + (text or "цена.количество"), 60, 528, "white")
            elif kind in ("buy8", "buy42", "sell5", "sell90", "invalid_qty"):
                rounded(pg, screen, pg.Rect(36, 518, 888, 42), COLORS['panel_alt'], 8)
                write(("B купить" if mode == "buy" else "S продать") + "  Количество: " + (text or "0"), 60, 528, "white")
            else:
                write("Стрелки — выбор позиции; Enter — продолжить; F10/Esc — выход", 60, 528, "cyan", small_font)
        else:
            card(pg, screen, pg.Rect(36, 105, 888, 405), COLORS['panel'], COLORS['border'])
            write(title, 64, 140, "yellow" if page else "white", title_font)
            for row, line in enumerate(lines):
                wrapped(line, 64, 202 + row * 28, "white")
            if kind == "f1":
                write("Нажмите F1", 64, 410, "danger")
            elif kind == "finish":
                write("Нажмите любую клавишу, чтобы выйти в меню FAST", 64, 456, "cyan")
            else:
                write("Enter/любая клавиша — следующий экран", 64, 456, "cyan")
        if status and time.monotonic() < status_until:
            rounded(pg, screen, pg.Rect(36, 518, 888, 42), COLORS['panel_alt'], 8)
            rounded(pg, screen, pg.Rect(36, 518, 888, 42), COLORS['warning'], 1, 2)
            write(status[:100], 60, 528, "yellow", small_font)
        rounded(pg, screen, pg.Rect(24, 572, 912, 20), COLORS['panel'], 6)
        write("F1 помощь   PgUp/PgDn экран   Home начало   F10/Esc выход", 42, 574, "muted", small_font)
        if help_visible:
            rounded(pg, screen, pg.Rect(190, 130, 580, 300), COLORS['background_alt'], 16)
            rounded(pg, screen, pg.Rect(190, 130, 580, 300), COLORS['accent'], 2, 2)
            write("Управление уроком", 236, 170, "white", title_font)
            for index, line in enumerate(("F1 - этот текст", "PgUp - следующий экран", "PgDn - предыдущий экран", "Home - первый экран", "F10, Esc - выход")):
                write(line, 246, 230 + index * 32, "white")
            write("F1 - закрыть помощь", 246, 390, "yellow", small_font)
        if confirm:
            rounded(pg, screen, pg.Rect(160, 220, 640, 150), COLORS['background_alt'], 16)
            rounded(pg, screen, pg.Rect(160, 220, 640, 150), COLORS['danger'], 2, 2)
            write("Завершить урок?", 230, 255, "white", title_font)
            write("Y / Enter — Да       N / Esc — Нет", 270, 315, "yellow")

    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False; continue
            if event.type != pg.KEYDOWN:
                continue
            key, kind = event.key, SCENES[page][2]
            if confirm:
                if key in (pg.K_y, pg.K_RETURN):
                    running = False
                elif key in (pg.K_n, pg.K_ESCAPE):
                    confirm = False
                continue
            if key == pg.K_F10:
                confirm = True
                continue
            if key == pg.K_ESCAPE:
                if kind == "cancel":
                    advance()
                elif kind in ("quote", "invalid_quote", "buy8", "buy42",
                              "sell5", "sell90", "invalid_qty"):
                    text, mode = "", ""
                    set_status("Ввод отменен")
                else:
                    confirm = True
                continue
            if key == pg.K_q:
                running = False; continue
            if key == pg.K_F1 and kind != "f1":
                help_visible = not help_visible
                continue
            if key == pg.K_HOME:
                page = 0; reset(page); continue
            if key == pg.K_PAGEUP:
                page = min(len(SCENES) - 1, page + 1); reset(page); continue
            if key == pg.K_PAGEDOWN:
                page = max(0, page - 1); reset(page); continue
            if kind == "f1":
                if key == pg.K_F1:
                    advance()
                continue
            if kind == "select":
                if key in (pg.K_LEFT, pg.K_RIGHT, pg.K_UP, pg.K_DOWN):
                    moved = True
                elif key == pg.K_RETURN and moved:
                    advance()
                continue
            if kind in ("quote", "invalid_quote"):
                if key == pg.K_BACKSPACE:
                    text = text[:-1]
                elif key in (pg.K_LEFT, pg.K_RIGHT):
                    side_choice = "bid" if key == pg.K_LEFT else "ask"
                elif key == pg.K_RETURN:
                    try:
                        price, quantity = _quote(text)
                        expected = {9: "50.10", 11: "33.1", 13: "54.99", 15: "123.5"}[page]
                        if text != expected:
                            raise ValueError
                        if page == 15 and side_choice != "ask":
                            set_status("Сначала выберите позицию Ask стрелкой")
                            continue
                        if kind == "invalid_quote":
                            raise OrderError
                        instrument, side = ((CPBND, "bid") if page == 9 else
                                            (ZCP, "bid") if page == 11 else
                                            (CPBND, "ask"))
                        book.submit(0, instrument, side, price, quantity)
                        set_status("Заявка принята"); advance()
                    except (ValueError, OrderError):
                        if kind == "invalid_quote" and text == "54.99":
                            set_status("Market rule violation"); advance()
                        else:
                            set_status("Неверный формат заявки"); text = ""
                elif event.unicode and event.unicode in "0123456789.":
                    text += event.unicode
                continue
            if kind in ("buy8", "buy42", "sell5", "sell90", "invalid_qty"):
                if key in (pg.K_b, pg.K_s) and not mode:
                    chosen = "buy" if key == pg.K_b else "sell"
                    required = "buy" if kind.startswith("buy") else "sell"
                    if chosen != required:
                        set_status("В этом шаге нужна клавиша " + ("B" if required == "buy" else "S"))
                    else:
                        mode, text = chosen, ""
                elif key == pg.K_BACKSPACE:
                    text = text[:-1]
                elif key == pg.K_RETURN and mode:
                    try:
                        quantity = _quantity(text)
                        expected = {"buy8": 8, "buy42": 42, "sell5": 5,
                                    "sell90": 90, "invalid_qty": 3}[kind]
                        if quantity != expected or kind == "invalid_qty":
                            raise OrderError
                        instrument = ZCP if mode == "buy" else CPBND
                        trade = book.take(0, instrument, mode, quantity)
                        if mode == "buy":
                            cash -= trade.price * quantity; holdings[instrument] += quantity
                        else:
                            cash += trade.price * quantity; holdings[instrument] -= quantity
                        set_status("Сделка совершена по цене " + str(trade.price)); advance()
                    except (ValueError, OrderError):
                        if kind == "invalid_qty" and text == "3":
                            set_status("Invalid quantity"); advance()
                        else:
                            set_status("Неверное количество"); text = ""
                elif event.unicode and event.unicode.isdigit():
                    text += event.unicode
                continue
            if kind == "cancel":
                if key == pg.K_ESCAPE:
                    advance()
                continue
            if kind == "finish":
                running = False; continue
            if kind == "market":
                if key in (pg.K_RETURN, pg.K_SPACE):
                    advance()
                continue
            if kind == "pause":
                if key not in (pg.K_LSHIFT, pg.K_RSHIFT, pg.K_LCTRL, pg.K_RCTRL,
                               pg.K_LALT, pg.K_RALT):
                    advance()
        draw()
        present_scaled(pg, screen, window)
        clock.tick(max(1, int(30 * max(0.1, min(float(speed), 10.0)))))
    if close_display:
        pg.quit()
