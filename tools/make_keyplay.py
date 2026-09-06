"""Build a tiny DOS BIOS keyboard replay TSR for reference experiments only.

No application bytes are modified. Each event is (BIOS ticks to wait, scan/ASCII).
Run KEYPLAY.COM before HEAD in a fresh emulator. Exit the emulator to remove TSR.
"""
from pathlib import Path
import struct


def build(events):
    # COM load address 0100h. CS overrides keep data independent of interrupted DS.
    code = bytearray()
    labels = {}
    fixups = []

    def emit(value):
        code.extend(bytes.fromhex(value))

    def address(name):
        fixups.append((len(code), name))
        code.extend(b'\0\0')

    emit('EB 00')  # short jump over resident handler, filled below
    labels['handler'] = len(code)
    emit('9C 50 53 51 52 1E')  # flags, AX BX CX DX DS
    emit('2E 8B 1E'); address('cursor')
    emit('2E 83 3F 00 74 17')  # delay zero means end; jump to restore
    emit('2E FF 0F 75 12')     # --delay; not ready -> restore
    emit('2E 8B 4F 02 B4 05 CD 16')  # BIOS store keystroke, CX scan/ASCII
    emit('83 C3 04 2E 89 1E'); address('cursor')
    emit('90 90')
    labels['restore'] = len(code)
    emit('1F 5A 59 5B 58 9D 2E FF 2E'); address('old')
    labels['old'] = len(code)
    emit('00 00 00 00')
    labels['cursor'] = len(code)
    address('events')
    labels['events'] = len(code)
    for delay, key in events:
        code.extend(struct.pack('<HH', delay, key))
    emit('00 00 00 00')
    labels['install'] = len(code)
    emit('B8 1C 35 CD 21 89 1E'); address('old')
    emit('8C 06'); address('old_segment')
    labels['old_segment'] = labels['old'] + 2
    emit('BA'); address('handler')
    emit('B8 1C 25 CD 21 BA')
    resident_paragraphs = (0x100 + labels['install'] + 15) // 16
    code.extend(struct.pack('<H', resident_paragraphs))
    emit('B8 00 31 CD 21')
    code[1] = labels['install'] - 2
    for offset, label in fixups:
        struct.pack_into('<H', code, offset, 0x100 + labels[label])
    return code


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('events', nargs='+', help='delay:hex-BIOS-key, e.g. 55:3920')
    args = parser.parse_args()
    args.output.write_bytes(build([(int(e.split(':')[0]), int(e.split(':')[1], 16)) for e in args.events]))
