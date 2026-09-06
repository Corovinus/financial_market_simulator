"""Readable formatting for the manual recovered from FAST.DOC."""
import re


_SUPERSCRIPT = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')


def pretty_formula(value):
    """Convert common plain-text math notation to readable Unicode math."""
    result = str(value).replace('`', '')
    for source, target in (
            ('Delta t', 'Δt'), ('delta t', 'δt'),
            ('Delta', 'Δ'), ('delta', 'δ'), ('sigma', 'σ'), ('mu', 'μ'),
            ('Sigma', 'Σ'), ('sqrt', '√'), (' >= ', ' ≥ '), (' <= ', ' ≤ '),
            (' != ', ' ≠ '), (' * ', ' · ')):
        result = result.replace(source, target)

    def exponent(match):
        return match.group(1).translate(_SUPERSCRIPT)

    return re.sub(r'\^([0-9+\-]+)', exponent, result)


def is_formula(value):
    """Recognize equation-like manual lines without treating table rules as math."""
    line = str(value).strip()
    if not line or line.count('=') > 4:
        return False
    has_number = any(character.isdigit() for character in line)
    equation = ('=' in line and any(mark in line for mark in
                                    ('+', '-', '*', '·', '/', '^', 'exp',
                                     'max', 'sqrt', '√', 'Δ', 'σ')))
    expression = any(mark in line for mark in ('²', '³', 'exp(', 'max (',
                                                   '√(', '$100/'))
    return has_number and (equation or expression)


def document_lines(text):
    """Clean DOS box edges while preserving the original document line order."""
    result = []
    for value in str(text).splitlines():
        line = value.strip().strip('│').strip()
        if set(line) <= set('─┌┐└┘├┤┬┴┼= ') and line:
            continue
        result.append(pretty_formula(line))
    return result


def table_of_contents(text, sections):
    """Resolve the numbered FAST.DOC contents into existing section names."""
    entries = []
    for line in str(text).splitlines():
        match = re.match(r'\s*\d+\.\|(.+?)\|\s*$', line)
        if match and match.group(1) in sections:
            entries.append(match.group(1))
    return entries
