"""Structured tables and mathematical typesetting for recovered FAST.DOC."""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re


_SUPERSCRIPT = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')


@dataclass(frozen=True)
class Fraction:
    numerator: str
    denominator: str


@dataclass(frozen=True)
class DocumentLine:
    kind: str
    text: str = ''
    parts: tuple = ()


@lru_cache(maxsize=2)
def load_sections(path):
    """Read the immutable converted manual once per process."""
    return json.loads(Path(path).read_text(encoding='utf-8'))


def pretty_formula(value):
    """Convert the notation used in FAST.DOC to conventional math glyphs."""
    result = str(value).replace('`', '')
    for source, target in (
            ('Delta t', 'Δt'), ('delta t', 'δt'),
            ('Delta', 'Δ'), ('delta', 'δ'), ('sigma', 'σ'), ('mu', 'μ'),
            ('Sigma', 'Σ'), ('sqrt', '√'), (' >= ', ' ≥ '), (' <= ', ' ≤ '),
            (' != ', ' ≠ '), (' * ', ' · ')):
        result = result.replace(source, target)
    if any(token in result for token in ('=', '^', '²', '³', 'exp(', 'max (')):
        result = result.replace('*', '·')

    def exponent(match):
        return match.group(1).translate(_SUPERSCRIPT)

    return re.sub(r'\^([0-9+\-]+)', exponent, result)


def _formula_parts(value):
    """Describe known FAST formulas with structural, horizontally ruled fractions."""
    line = pretty_formula(value).strip()

    match = re.match(
        r'(Очки|ОЧКИ) = \((Сумма денег .+?) / (9999)\) · (\$[46])$', line)
    if match:
        return (match.group(1) + ' = ', Fraction(match.group(2), '9 999'),
                ' · ' + match.group(4))

    match = re.match(
        r'ОЧКИ = 4 \+ 4 · \((.+?)\) / \((9999-5000)\)$', line)
    if match:
        return ('ОЧКИ = 4 + 4 · ',
                Fraction(match.group(1).replace(' - ', ' − '), '9 999 − 5 000'))

    match = re.match(r'ОЧКИ = 8 \+ \((.+?)\) / (\$9500)$', line)
    if match:
        return ('ОЧКИ = 8 + ',
                Fraction(match.group(1).replace(' - ', ' − '), '$9 500'))

    if line.startswith('$100/(1.15)²'):
        return ('3-летняя: ', Fraction('$100', '1.15²'), '     2-летняя: ',
                Fraction('$100', '1.15'))

    match = re.match(r'u = exp\((.+?)/√\(?(.+?)\)?\)$', line)
    if match:
        return ('u = exp(', Fraction(match.group(1), '√' + match.group(2)), ')')

    match = re.match(r'd = 1/(.+)$', line)
    if match:
        return ('d = ', Fraction('1', match.group(1)))

    match = re.match(r'p = \( exp\((.+?)/(.+?)\) - d \) / \((.+?)\)$', line)
    if match:
        rate = ('0.01' if match.group(1) == '0.12' and match.group(2) == '12'
                else f'{match.group(1)} / {match.group(2)}')
        inner = f'exp({rate}) − d'
        return ('p = ', Fraction(inner, match.group(3).replace(' - ', ' − ')))

    # Remaining documented equations contain products, powers or max(), but no
    # division requiring a fraction bar.
    return (line.replace(' - ', ' − '),)


def is_formula(value):
    if isinstance(value, DocumentLine):
        return value.kind == 'formula'
    line = pretty_formula(value).strip()
    if not line or line.count('=') > 4:
        return False
    has_number = any(character.isdigit() for character in line)
    equation = ('=' in line and any(mark in line for mark in
                                    ('+', ' - ', '*', '·', '/', 'exp', 'max',
                                     '√', 'Δ', 'σ')))
    expression = any(mark in line for mark in ('²', '³', 'exp(', 'max (',
                                                   '√(', '$100/'))
    return equation or (has_number and expression)


def _plain_or_formula(value):
    text = pretty_formula(value.strip())
    portfolio = re.search(
        r'Для\s+портфеля B это число равно \(\s*([0-9]+) \+ ([0-9]+)\) · 0.5 = ([0-9.]+)',
        text)
    if portfolio:
        text = (f'Портфель B = ({portfolio.group(1)} + {portfolio.group(2)}) '
                f'· 0.5 = {portfolio.group(3)}')
    utility = re.match(
        r'^[\[(]*([0-9.]+)·\(Наличные деньги\s*([+-])\s*([0-9.]+)\s*·\s*Наличные деньги²\)',
        text)
    if utility:
        sign = '−' if utility.group(2) == '-' else '+'
        text = (f'Промежуточные очки = {utility.group(1)} · '
                f'(Наличные деньги {sign} {utility.group(3)} · Наличные деньги²)')
    return DocumentLine('formula', text, _formula_parts(text)) if is_formula(text) else DocumentLine('text', text)


def _looks_tabular(value):
    """Recognize fixed-width columns without confusing justified DOS prose."""
    cells = re.split(r'\s{2,}', value.strip())
    if len(cells) < 3:
        return False
    numeric = sum(bool(re.fullmatch(r'[$#.%+\-0-9 ]+', cell))
                  for cell in cells)
    code_and_price = (bool(re.fullmatch(r'[A-Z0-9, ]+', cells[-2])) and
                      bool(re.search(r'\$|руб|[0-9]', cells[-1])))
    compact_header = (
        len(cells) <= 6 and
        all(len(cell) <= 30 and len(cell.split()) <= 4 for cell in cells) and
        not any(cell.endswith((',', '.', '-', ';')) for cell in cells))
    return numeric >= 2 or code_and_price or compact_header


def document_lines(text):
    """Classify paragraphs, table rows and every equation found in FAST.DOC."""
    result = []
    source = str(text).splitlines()
    index = 0
    while index < len(source):
        value = source[index]
        if (value.strip().strip('`').endswith('sigma^2 *') and index + 1 < len(source) and
                source[index + 1].strip().strip('`').startswith('Delta t')):
            value = value.rstrip().rstrip('`')[:-1] + source[index + 1].strip().strip('`')
            index += 1
        stripped = value.strip()
        if not stripped:
            result.append(DocumentLine('text'))
            index += 1
            continue
        if set(stripped) <= set('─┌┐└┘├┤┬┴┼= '):
            index += 1
            continue
        if '│' in value:
            row = value.strip().strip('│')
            header = '=' in row
            row = re.sub(r'={2,}', ' ', row).strip()
            result.append(DocumentLine('table_header' if header else 'table',
                                       pretty_formula(row)))
            index += 1
            continue
        line = stripped.replace('`', '')
        if 'sigma^2' in line and 'Delta t' in line:
            result.extend((
                DocumentLine('text', 'Ожидаемая доходность акции:'),
                DocumentLine('formula', 'μ · Δt', ('μ · Δt',)),
                DocumentLine('text', 'Вариация доходности акции:'),
                DocumentLine('formula', 'σ² · Δt', ('σ² · Δt',)),
            ))
            index += 1
            continue
        # The binomial parameters are three separate equations. Splitting them
        # prevents a long line and lets each quotient receive its own bar.
        if line.startswith('u = exp(') and ';' in line:
            result.extend(_plain_or_formula(part.strip().rstrip('.'))
                          for part in line.split(';'))
            index += 1
            continue
        classified = _plain_or_formula(line)
        if classified.kind == 'formula':
            result.append(classified)
            index += 1
            continue
        if _looks_tabular(line):
            kind = ('table_header' if not any(character.isdigit()
                                               for character in line)
                    else 'table')
            result.append(DocumentLine(kind, pretty_formula(line)))
            index += 1
            continue
        result.append(classified)
        index += 1
    return result


def line_text(value):
    return value.text if isinstance(value, DocumentLine) else str(value)


def line_height(value):
    if isinstance(value, DocumentLine) and value.kind == 'formula':
        return 42 if any(isinstance(part, Fraction) for part in value.parts) else 28
    return 20 if (isinstance(value, DocumentLine) and
                  value.kind in ('table', 'table_header')) else 19


def page_scroll(values, start, direction, height):
    """Move by one visual page without skipping variable-height rows."""
    if not values or direction == 0:
        return max(0, start)
    start = max(0, min(start, len(values) - 1))
    if direction > 0:
        used = 0
        index = start
        while index < len(values) and (used == 0 or used + line_height(values[index]) <= height):
            used += line_height(values[index])
            index += 1
        return min(len(values) - 1, index)
    used = 0
    index = start
    while index > 0 and (used == 0 or used + line_height(values[index - 1]) <= height):
        index -= 1
        used += line_height(values[index])
    return index


def draw_document_line(pygame, surface, value, rect, text_font, math_font,
                       table_font, colors):
    """Draw one classified line and return its actual vertical height."""
    kind = value.kind if isinstance(value, DocumentLine) else 'text'
    text = line_text(value)
    height = line_height(value)
    if kind in ('table', 'table_header'):
        fill = colors['panel_alt'] if kind == 'table_header' else colors['background_alt']
        pygame.draw.rect(surface, fill,
                         (rect.x, rect.y, rect.width, height))
        pygame.draw.line(surface, colors['border'],
                         (rect.x, rect.y + height - 1),
                         (rect.x + rect.width, rect.y + height - 1))
        pygame.draw.rect(surface, colors['accent_alt'],
                         (rect.x, rect.y, 3, height))
        color = colors['accent_alt'] if kind == 'table_header' else colors['text']
        image = table_font.render(text, True, color)
        surface.blit(image, (rect.x + 9, rect.y + 3))
    elif kind == 'formula':
        pygame.draw.rect(surface, colors['background_alt'],
                         (rect.x, rect.y, rect.width, height), border_radius=6)
        parts = value.parts or (text,)
        widths = []
        for part in parts:
            if isinstance(part, Fraction):
                widths.append(max(math_font.size(part.numerator)[0],
                                  math_font.size(part.denominator)[0]) + 12)
            else:
                widths.append(math_font.size(part)[0])
        x = rect.x + max(12, (rect.width - sum(widths)) // 2)
        for part, width in zip(parts, widths):
            if isinstance(part, Fraction):
                numerator = math_font.render(part.numerator, True,
                                             colors['accent_alt'])
                denominator = math_font.render(part.denominator, True,
                                               colors['accent_alt'])
                surface.blit(numerator, (x + (width - numerator.get_width()) // 2,
                                         rect.y + 2))
                bar_y = rect.y + 19
                pygame.draw.line(surface, colors['accent_alt'],
                                 (x + 2, bar_y), (x + width - 2, bar_y), 1)
                surface.blit(denominator,
                             (x + (width - denominator.get_width()) // 2,
                              rect.y + 21))
            else:
                image = math_font.render(part, True, colors['accent_alt'])
                surface.blit(image, (x, rect.y + (height - image.get_height()) // 2))
            x += width
    else:
        image = text_font.render(text, True, colors['text'])
        surface.blit(image, (rect.x + 6, rect.y + 2))
    return height


def table_of_contents(text, sections):
    """Resolve the numbered FAST.DOC contents into existing section names."""
    entries = []
    for line in str(text).splitlines():
        match = re.match(r'\s*\d+\.\|(.+?)\|\s*$', line)
        if match and match.group(1) in sections:
            entries.append(match.group(1))
    return entries
