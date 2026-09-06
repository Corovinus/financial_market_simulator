"""16-bit MZ disassembly with file offsets; data can also decode as instructions."""
import argparse
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('exe', type=Path)
parser.add_argument('--start', type=lambda s: int(s, 0))
parser.add_argument('--length', type=lambda s: int(s, 0), default=512)
args = parser.parse_args()
data = args.exe.read_bytes()
header = struct.unpack_from('<H', data, 8)[0] * 16
ip, cs = struct.unpack_from('<HH', data, 20)
start = args.start if args.start is not None else header + cs * 16 + ip
decoder = Cs(CS_ARCH_X86, CS_MODE_16)
decoder.skipdata = True
print(f'; {args.exe.name}: header={header:#x}; entry={header + cs * 16 + ip:#x}; file offsets below')
for op in decoder.disasm(data[start:start + args.length], start):
    print(f'{op.address:06X}  {op.bytes.hex():24} {op.mnemonic:8} {op.op_str}')
