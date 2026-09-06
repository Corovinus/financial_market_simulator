"""Preserve CP866 text and byte-offset-labelled DOS executable strings."""
from pathlib import Path
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
PURPOSES = {
    'FAST.BAT': 'Русификатор, видеосовместимость, цикл меню и диспетчер запуска',
    'INSTALL.BAT': 'DOS-установка комплекта на другой диск',
    'B01.PAR': 'Параметры купонной и бескупонной облигации для BIDASK',
    'B02.PAR': 'Параметры четырёх облигаций с переменными ставками для BIDASK',
    'B03.EXE': 'Облигации и фьючерсы', 'B04.EXE': 'Неопределённая процентная ставка',
    'BIDASK.EXE': 'Общий двойной аукцион и роботы B01/B02',
    'CA1.EXE': 'Рынок акций: избегание риска', 'CA2.EXE': 'Фиксированные цены акций',
    'CA3.EXE': 'Рынок акций: склонность к риску', 'DEMO.EXE': 'Проигрыватель учебных слайдов',
    'HEAD.EXE': 'Диспетчер модулей и служебный компонент запуска',
    'OP1.EXE': 'Однопериодные опционы', 'OP2.EXE': 'Двухпериодные опционы',
    'OP3.EXE': 'Дельта-хеджирование', 'RE1.EXE': 'Информационная эффективность',
    'RE2.EXE': 'Эффективность портфеля', 'RE3.EXE': 'Информация и опционы',
    'STEND.EXE': 'Главное меню и просмотр гипертекста',
    'TUTBO.EXE': 'Учебный расчёт дюрации и иммунизации',
    'TUTCA.EXE': 'Учебная модель CAPM и конкурентного равновесия',
    'TUTOP.EXE': 'Учебные опционные портфели и стратегии',
    'STEND.MNU': 'Бинарный ресурс меню, не текстовый конфиг',
    'FTS_TUT.SLD': 'Бинарные слайды знакомства с двойным аукционом',
    'SERIAL#.FTS': 'Серийные данные; точное использование пока не установлено',
    'PROBLEMS': 'Текст учебных задач, не параметры торгов',
    'RESULTS': 'Историческая таблица результатов обучения (Минск, 1995)',
    'KEYRUS.COM': 'Русификатор клавиатуры и экранных шрифтов',
    'EGAVGA.BGI': 'Драйвер Borland EGA/VGA',
    'FAST.DOC': 'Гипертекстовая документация CP866 с разделами @ и ссылками |...|',
    'NOLFB.COM': 'Предположительно отключение linear framebuffer; алгоритм не исследован',
}


def main():
    output = ROOT / 'data' / 'converted'
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for path in sorted((ROOT / 'data' / 'original').iterdir()):
        data = path.read_bytes()
        entry = dict(name=path.name, size=len(data), sha256=hashlib.sha256(data).hexdigest())
        entry['purpose'] = PURPOSES.get(path.name.upper(), 'Однобайтный параметр #; смысл пока UNKNOWN')
        if data.startswith(b'MZ'):
            entry['type'] = 'DOS MZ executable'
            fields = struct.unpack_from('<14H', data)
            entry['mz'] = dict(zip(('signature', 'last_page_bytes', 'pages', 'relocations', 'header_paragraphs', 'min_alloc', 'max_alloc', 'ss', 'sp', 'checksum', 'ip', 'cs', 'relocation_offset', 'overlay'), fields))
            lines = [f'{m.start():06X}\t{m.group().decode("cp866")}' for m in re.finditer(rb'[\x20-\x7e\x80-\xff]{4,}', data)]
            (output / (path.name + '.strings.txt')).write_text('\n'.join(lines), encoding='utf-8')
        elif path.suffix.upper() in ('.COM', '.BGI', '.MNU', '.SLD'):
            entry['type'] = {'.COM': 'DOS COM executable', '.BGI': 'Borland graphics driver', '.MNU': 'binary menu resource', '.SLD': 'binary tutorial slideshow'}[path.suffix.upper()]
            lines = [f'{m.start():06X}\t{m.group().decode("cp866")}' for m in re.finditer(rb'[\x20-\x7e\x80-\xff]{4,}', data)]
            (output / (path.name + '.strings.txt')).write_text('\n'.join(lines), encoding='utf-8')
        else:
            entry['type'] = 'CP866 text/data (classification requires inspection)'
            (output / (path.name + '.txt')).write_text(data.decode('cp866').replace('\r\n', '\n'), encoding='utf-8', newline='\n')
        inventory.append(entry)
    (output / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    table = ['# Полный инвентарь образа', '', '| Имя | Байты | Тип | Назначение |', '|---|---:|---|---|']
    table.extend(f'| {e["name"]} | {e["size"]} | {e["type"]} | {e["purpose"]} |' for e in inventory)
    (ROOT / 'FILE_INVENTORY.md').write_text('\n'.join(table) + '\n', encoding='utf-8')
    doc = (ROOT / 'data/original/FAST.DOC').read_bytes().decode('cp866')
    sections = {part.splitlines()[0]: '\n'.join(part.splitlines()[1:]) for part in re.split(r'(?m)^@', doc) if part.strip()}
    (output / 'manual_sections.json').write_text(json.dumps(sections, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
