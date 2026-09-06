from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
import sys
p=Path(sys.argv[1]).read_bytes(); start=int(sys.argv[2],0); end=start+int(sys.argv[3],0); dec=Cs(CS_ARCH_X86,CS_MODE_16); dec.skipdata=True
while start<min(end,len(p)):
 b=p[start:start+20]; extra=0; note=''
 if b[0]==0xcd and 0x34<=b[1]<=0x3b:
  b=bytes([b[1]+0xa4])+b[2:]; extra=1; note='; emulated x87'
 elif b[:2]==b'\xcd\x3c' and 0x98<=b[2]<=0x9f:
  b=bytes([0x2e,b[2]+0x40])+b[3:]; extra=1; note='; emulated x87 CS'
 elif b[:2]==b'\xcd\x3d':
  b=b'\x9b'+b[2:]; extra=1; note='; emulated fwait'
 op=next(dec.disasm(b,start,count=1)); length=op.size+extra
 print(f'{start:06X}  {p[start:start+length].hex():24} {op.mnemonic:8} {op.op_str} {note}')
 start+=length
