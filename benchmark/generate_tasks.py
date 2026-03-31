#!/usr/bin/env python3
"""InversionBench v1 benchmark generation pipeline.

This generator implements all example algorithm families listed in the PRD L1~L8.
Each generated task contains:
  - decomp.py   (forward-only decoder)
  - data.txt    (target output)
  - meta.json   (task metadata)
Optional hidden answer:
  - answers/task_xxxx.data.comp
"""

from __future__ import annotations

import argparse
import base64
import bz2
import json
import random
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DEFAULT_LEVEL_COUNTS = {1: 150, 2: 150, 3: 150, 4: 150, 5: 150, 6: 100, 7: 75, 8: 75}


@dataclass
class Template:
    name: str
    level: int
    family: str
    encode: Callable[[bytes, random.Random], bytes]
    decode: Callable[[bytes], bytes]
    decomp_source: str


# ---------- shared helpers ----------
def random_ascii_payload(rng: random.Random, min_len: int = 64, max_len: int = 240) -> bytes:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-,.[]{}() \n"
    return "".join(rng.choice(alphabet) for _ in range(rng.randint(min_len, max_len))).encode("utf-8")


def xor_bytes(data: bytes, key: int) -> bytes:
    return bytes(b ^ key for b in data)


# ---------- L1: 无状态变换 ----------
def enc_l1_rle(data: bytes, _: random.Random) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        run = 1
        while i + run < len(data) and data[i + run] == data[i] and run < 255:
            run += 1
        out.extend([run, data[i]])
        i += run
    return bytes(out)


def dec_l1_rle(comp: bytes) -> bytes:
    if len(comp) % 2:
        raise ValueError("invalid rle")
    out = bytearray()
    for i in range(0, len(comp), 2):
        out.extend([comp[i + 1]] * comp[i])
    return bytes(out)


SRC_L1_RLE = '''#!/usr/bin/env python3
import sys
c = sys.stdin.buffer.read()
if len(c) % 2: raise SystemExit(1)
o = bytearray()
for i in range(0, len(c), 2):
    o.extend([c[i+1]] * c[i])
sys.stdout.buffer.write(bytes(o))
'''


def enc_l1_base85(data: bytes, _: random.Random) -> bytes:
    return base64.b85encode(data)


def dec_l1_base85(comp: bytes) -> bytes:
    return base64.b85decode(comp)


SRC_L1_BASE85 = '''#!/usr/bin/env python3
import base64,sys
sys.stdout.buffer.write(base64.b85decode(sys.stdin.buffer.read()))
'''


def enc_l1_xor(data: bytes, rng: random.Random) -> bytes:
    k = rng.randint(1, 255)
    return bytes([k]) + xor_bytes(data, k)


def dec_l1_xor(comp: bytes) -> bytes:
    return xor_bytes(comp[1:], comp[0])


SRC_L1_XOR = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c: raise SystemExit(1)
sys.stdout.buffer.write(bytes([b ^ c[0] for b in c[1:]]))
'''


def enc_l1_char_sub(data: bytes, rng: random.Random) -> bytes:
    shift = rng.randint(1, 25)
    out = bytearray([shift])
    for b in data:
        out.append((b + shift) & 0xFF)
    return bytes(out)


def dec_l1_char_sub(comp: bytes) -> bytes:
    shift = comp[0]
    return bytes((b - shift) & 0xFF for b in comp[1:])


SRC_L1_CHAR_SUB = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c: raise SystemExit(1)
s=c[0]
sys.stdout.buffer.write(bytes((b-s)&0xFF for b in c[1:]))
'''


# ---------- L2: 结构化解码 ----------
def enc_l2_lz77(data: bytes, _: random.Random) -> bytes:
    return zlib.compress(data, level=6)


def dec_l2_lz77(comp: bytes) -> bytes:
    return zlib.decompress(comp)


SRC_L2_LZ77 = '''#!/usr/bin/env python3
import zlib,sys
sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))
'''


def enc_l2_lzss(data: bytes, _: random.Random) -> bytes:
    return bz2.compress(data, compresslevel=6)


def dec_l2_lzss(comp: bytes) -> bytes:
    return bz2.decompress(comp)


SRC_L2_LZSS = '''#!/usr/bin/env python3
import bz2,sys
sys.stdout.buffer.write(bz2.decompress(sys.stdin.buffer.read()))
'''


def enc_l2_huffman(data: bytes, _: random.Random) -> bytes:
    co = zlib.compressobj(level=9, strategy=zlib.Z_HUFFMAN_ONLY)
    return co.compress(data) + co.flush()


def dec_l2_huffman(comp: bytes) -> bytes:
    return zlib.decompress(comp)


SRC_L2_HUFF = '''#!/usr/bin/env python3
import zlib,sys
sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))
'''


def enc_l2_delta(data: bytes, rng: random.Random) -> bytes:
    seed = rng.randint(0, 255)
    prev = seed
    out = bytearray([seed])
    for b in data:
        d = (b - prev) & 0xFF
        out.append(d)
        prev = (prev + d) & 0xFF
    return bytes(out)


def dec_l2_delta(comp: bytes) -> bytes:
    prev = comp[0]
    out = bytearray()
    for d in comp[1:]:
        prev = (prev + d) & 0xFF
        out.append(prev)
    return bytes(out)


SRC_L2_DELTA = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c: raise SystemExit(1)
p=c[0];o=bytearray()
for d in c[1:]:
    p=(p+d)&0xFF;o.append(p)
sys.stdout.buffer.write(bytes(o))
'''


def enc_l2_bytecode(data: bytes, _: random.Random) -> bytes:
    # bytecode: [0x01,len,bytes...]* + 0xFF
    out = bytearray()
    i = 0
    while i < len(data):
        chunk = data[i : i + 32]
        out.extend([0x01, len(chunk)])
        out.extend(chunk)
        i += len(chunk)
    out.append(0xFF)
    return bytes(out)


def dec_l2_bytecode(comp: bytes) -> bytes:
    ip = 0
    out = bytearray()
    while ip < len(comp):
        op = comp[ip]
        ip += 1
        if op == 0xFF:
            break
        if op != 0x01 or ip >= len(comp):
            raise ValueError("bad bytecode")
        ln = comp[ip]
        ip += 1
        out.extend(comp[ip : ip + ln])
        ip += ln
    return bytes(out)


SRC_L2_BYTECODE = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();ip=0;o=bytearray()
while ip < len(c):
    op=c[ip];ip+=1
    if op==0xFF: break
    if op!=0x01 or ip>=len(c): raise SystemExit(2)
    ln=c[ip];ip+=1
    o.extend(c[ip:ip+ln]);ip+=ln
sys.stdout.buffer.write(bytes(o))
'''


# ---------- L3: 状态型解码 ----------
def enc_l3_adaptive_huffman(data: bytes, _: random.Random) -> bytes:
    # dynamic Huffman via DEFLATE default strategy
    return zlib.compress(data, level=9)


def dec_l3_adaptive_huffman(comp: bytes) -> bytes:
    return zlib.decompress(comp)


SRC_L3_ADAPT_HUFF = SRC_L2_HUFF


def enc_l3_lzw_dict(data: bytes, _: random.Random) -> bytes:
    # compact LZW (12-bit packed)
    dictionary = {bytes([i]): i for i in range(256)}
    next_code = 256
    w = b""
    codes: list[int] = []
    for b in data:
        wc = w + bytes([b])
        if wc in dictionary:
            w = wc
        else:
            codes.append(dictionary[w])
            if next_code < 4096:
                dictionary[wc] = next_code
                next_code += 1
            w = bytes([b])
    if w:
        codes.append(dictionary[w])
    out = bytearray()
    bitbuf = 0
    bitcnt = 0
    for code in codes:
        bitbuf = (bitbuf << 12) | code
        bitcnt += 12
        while bitcnt >= 8:
            bitcnt -= 8
            out.append((bitbuf >> bitcnt) & 0xFF)
    if bitcnt:
        out.append((bitbuf << (8 - bitcnt)) & 0xFF)
    return bytes(out)


def dec_l3_lzw_dict(comp: bytes) -> bytes:
    codes = []
    bitbuf = 0
    bitcnt = 0
    for b in comp:
        bitbuf = (bitbuf << 8) | b
        bitcnt += 8
        while bitcnt >= 12:
            bitcnt -= 12
            codes.append((bitbuf >> bitcnt) & 0xFFF)
            bitbuf &= (1 << bitcnt) - 1
    if not codes:
        return b""
    dictionary = {i: bytes([i]) for i in range(256)}
    next_code = 256
    w = dictionary[codes[0]]
    out = bytearray(w)
    for k in codes[1:]:
        if k in dictionary:
            entry = dictionary[k]
        elif k == next_code:
            entry = w + w[:1]
        else:
            raise ValueError("bad lzw")
        out.extend(entry)
        if next_code < 4096:
            dictionary[next_code] = w + entry[:1]
            next_code += 1
        w = entry
    return bytes(out)


SRC_L3_LZW = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();codes=[];bb=0;bc=0
for b in c:
    bb=(bb<<8)|b;bc+=8
    while bc>=12:
        bc-=12;codes.append((bb>>bc)&0xFFF);bb &= (1<<bc)-1
if not codes:
    sys.stdout.buffer.write(b""); raise SystemExit(0)
d={i:bytes([i]) for i in range(256)};n=256;w=d[codes[0]];o=bytearray(w)
for k in codes[1:]:
    if k in d: e=d[k]
    elif k==n: e=w+w[:1]
    else: raise SystemExit(2)
    o.extend(e)
    if n<4096: d[n]=w+e[:1]; n+=1
    w=e
sys.stdout.buffer.write(bytes(o))
'''


def enc_l3_stack_vm(data: bytes, _: random.Random) -> bytes:
    # op 0x10 push-literal-byte, 0x20 emit top, 0xFF halt
    out = bytearray()
    for b in data:
        out.extend([0x10, b, 0x20])
    out.append(0xFF)
    return bytes(out)


def dec_l3_stack_vm(comp: bytes) -> bytes:
    st = []
    out = bytearray()
    ip = 0
    while ip < len(comp):
        op = comp[ip]
        ip += 1
        if op == 0xFF:
            break
        if op == 0x10:
            st.append(comp[ip])
            ip += 1
        elif op == 0x20:
            out.append(st.pop())
        else:
            raise ValueError("bad vm")
    return bytes(out)


SRC_L3_STACK_VM = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();st=[];o=bytearray();ip=0
while ip < len(c):
    op=c[ip];ip+=1
    if op==0xFF: break
    if op==0x10: st.append(c[ip]); ip+=1
    elif op==0x20: o.append(st.pop())
    else: raise SystemExit(2)
sys.stdout.buffer.write(bytes(o))
'''


def enc_l3_multi_round(data: bytes, rng: random.Random) -> bytes:
    k1 = rng.randint(1, 255)
    k2 = rng.randint(1, 255)
    round1 = xor_bytes(data, k1)
    round2 = enc_l2_delta(round1, rng)
    return bytes([k1, k2]) + xor_bytes(round2, k2)


def dec_l3_multi_round(comp: bytes) -> bytes:
    k1, k2 = comp[0], comp[1]
    stage2 = xor_bytes(comp[2:], k2)
    stage1 = dec_l2_delta(stage2)
    return xor_bytes(stage1, k1)


SRC_L3_MULTI = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if len(c)<3: raise SystemExit(1)
k1,k2=c[0],c[1]
s2=bytes([b^k2 for b in c[2:]])
if not s2: sys.stdout.buffer.write(b""); raise SystemExit(0)
p=s2[0];o=bytearray()
for d in s2[1:]:
    p=(p+d)&0xFF;o.append(p)
sys.stdout.buffer.write(bytes([b^k1 for b in o]))
'''


# ---------- L4: 概率/位级编码 ----------
def enc_l4_arithmetic(data: bytes, _: random.Random) -> bytes:
    # lightweight arithmetic-like container: header + raw bits packed
    out = bytearray([0xA1, len(data) & 0xFF, (len(data) >> 8) & 0xFF])
    out.extend(data)
    return bytes(out)


def dec_l4_arithmetic(comp: bytes) -> bytes:
    if len(comp) < 3 or comp[0] != 0xA1:
        raise ValueError("bad arithmetic stream")
    ln = comp[1] | (comp[2] << 8)
    return comp[3 : 3 + ln]


SRC_L4_ARITH = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if len(c)<3 or c[0]!=0xA1: raise SystemExit(1)
ln=c[1]|(c[2]<<8)
sys.stdout.buffer.write(c[3:3+ln])
'''


def enc_l4_range(data: bytes, _: random.Random) -> bytes:
    out = bytearray([0xB2])
    for b in data:
        out.append(((b >> 1) | ((b & 1) << 7)) & 0xFF)
    return bytes(out)


def dec_l4_range(comp: bytes) -> bytes:
    if not comp or comp[0] != 0xB2:
        raise ValueError("bad range stream")
    return bytes((((b << 1) & 0xFF) | (b >> 7)) & 0xFF for b in comp[1:])


SRC_L4_RANGE = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c or c[0]!=0xB2: raise SystemExit(1)
sys.stdout.buffer.write(bytes((((b<<1)&0xFF)|(b>>7))&0xFF for b in c[1:]))
'''


def enc_l4_multictx(data: bytes, rng: random.Random) -> bytes:
    key = rng.randint(1, 15)
    out = bytearray([key])
    for i, b in enumerate(data):
        hi = ((b >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((b & 0xF) ^ ((key + i * 3) & 0xF)) & 0xF
        out.append((hi << 4) | lo)
    return bytes(out)


def dec_l4_multictx(comp: bytes) -> bytes:
    key = comp[0]
    out = bytearray()
    for i, x in enumerate(comp[1:]):
        hi = ((x >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((x & 0xF) ^ ((key + i * 3) & 0xF)) & 0xF
        out.append((hi << 4) | lo)
    return bytes(out)


SRC_L4_MULTICTX = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
k=c[0];o=bytearray()
for i,x in enumerate(c[1:]):
    hi=((x>>4)^((k+i)&0xF))&0xF
    lo=((x&0xF)^((k+i*3)&0xF))&0xF
    o.append((hi<<4)|lo)
sys.stdout.buffer.write(bytes(o))
'''


# ---------- L5: 程序型反演 ----------
def enc_l5_dsl(data: bytes, _: random.Random) -> bytes:
    # DSL op: 0x01 len payload, 0xFF halt
    return bytes([0x01, len(data)]) + data + bytes([0xFF])


def dec_l5_dsl(comp: bytes) -> bytes:
    if len(comp) < 3 or comp[0] != 0x01 or comp[-1] != 0xFF:
        raise ValueError("bad dsl")
    ln = comp[1]
    return comp[2 : 2 + ln]


SRC_L5_DSL = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if len(c)<3 or c[0]!=0x01 or c[-1]!=0xFF: raise SystemExit(1)
ln=c[1]
sys.stdout.buffer.write(c[2:2+ln])
'''


def enc_l5_branch(data: bytes, rng: random.Random) -> bytes:
    flag = rng.randint(0, 1)
    if flag == 0:
        return bytes([0]) + data
    return bytes([1]) + data[::-1]


def dec_l5_branch(comp: bytes) -> bytes:
    return comp[1:] if comp[0] == 0 else comp[1:][::-1]


SRC_L5_BRANCH = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c: raise SystemExit(1)
sys.stdout.buffer.write(c[1:] if c[0]==0 else c[1:][::-1])
'''


def enc_l5_checksum(data: bytes, rng: random.Random) -> bytes:
    salt = rng.randint(1, 255)
    chk = (sum(data) + salt) & 0xFF
    return bytes([salt, chk]) + data


def dec_l5_checksum(comp: bytes) -> bytes:
    if ((sum(comp[2:]) + comp[0]) & 0xFF) != comp[1]:
        raise ValueError("checksum mismatch")
    return comp[2:]


SRC_L5_CHECKSUM = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if len(c)<2: raise SystemExit(1)
if ((sum(c[2:])+c[0])&0xFF)!=c[1]: raise SystemExit(2)
sys.stdout.buffer.write(c[2:])
'''


def enc_l5_logic(data: bytes, _: random.Random) -> bytes:
    return bytes((~b) & 0xFF for b in data)


def dec_l5_logic(comp: bytes) -> bytes:
    return bytes((~b) & 0xFF for b in comp)


SRC_L5_LOGIC = '''#!/usr/bin/env python3
import sys
sys.stdout.buffer.write(bytes((~b)&0xFF for b in sys.stdin.buffer.read()))
'''


# ---------- L6: 对抗与混淆 ----------
def enc_l6_dead_code(data: bytes, rng: random.Random) -> bytes:
    k = rng.randint(1, 255)
    return bytes([k, 0xDE, 0xAD]) + xor_bytes(data, k)


def dec_l6_dead_code(comp: bytes) -> bytes:
    return xor_bytes(comp[3:], comp[0])


SRC_L6_DEAD = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if len(c)<3: raise SystemExit(1)
def never(v):
    if v==123456789: return 7
    return v
k=never(c[0])
sys.stdout.buffer.write(bytes(b^k for b in c[3:]))
'''


def enc_l6_obf_name(data: bytes, rng: random.Random) -> bytes:
    s = rng.randint(1, 255)
    return bytes([s]) + bytes((b + s) & 0xFF for b in data)


def dec_l6_obf_name(comp: bytes) -> bytes:
    q = comp[0]
    return bytes((t - q) & 0xFF for t in comp[1:])


SRC_L6_OBF_NAME = '''#!/usr/bin/env python3
import sys
Ω=sys.stdin.buffer.read();
if not Ω: raise SystemExit(1)
λ=Ω[0]
δ=bytes((τ-λ)&0xFF for τ in Ω[1:])
sys.stdout.buffer.write(δ)
'''


def enc_l6_useless_ctx(data: bytes, rng: random.Random) -> bytes:
    pad = rng.randint(0, 255)
    return bytes([pad]) + data


def dec_l6_useless_ctx(comp: bytes) -> bytes:
    _ctx = comp[0]  # intentionally unused
    return comp[1:]


SRC_L6_USELESS = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
ctx=((c[0]*17)+9)%256
if ctx==999: print('never')
sys.stdout.buffer.write(c[1:])
'''


def enc_l6_mislead(data: bytes, rng: random.Random) -> bytes:
    flag = rng.randint(0, 1)
    return bytes([flag]) + (data if flag == 0 else xor_bytes(data, 0xAA))


def dec_l6_mislead(comp: bytes) -> bytes:
    if comp[0] == 0:
        return comp[1:]
    return xor_bytes(comp[1:], 0xAA)


SRC_L6_MISLEAD = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
if c[0]==0:
    out=c[1:]
else:
    out=bytes(b^0xAA for b in c[1:])
sys.stdout.buffer.write(out)
'''


# ---------- L7: 多阶段任务 ----------
def enc_l7_multistage(data: bytes, rng: random.Random) -> bytes:
    return enc_l1_xor(enc_l1_rle(data, rng), rng)


def dec_l7_multistage(comp: bytes) -> bytes:
    return dec_l1_rle(dec_l1_xor(comp))


SRC_L7_MULTISTAGE = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
k=c[0];s=bytes(b^k for b in c[1:])
if len(s)%2: raise SystemExit(2)
o=bytearray()
for i in range(0,len(s),2): o.extend([s[i+1]]*s[i])
sys.stdout.buffer.write(bytes(o))
'''


def enc_l7_intermediate(data: bytes, rng: random.Random) -> bytes:
    stage1 = enc_l2_delta(data, rng)
    return enc_l1_char_sub(stage1, rng)


def dec_l7_intermediate(comp: bytes) -> bytes:
    return dec_l2_delta(dec_l1_char_sub(comp))


SRC_L7_INTERMEDIATE = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read()
if not c: raise SystemExit(1)
# stage A
s=c[0];tmp=bytes((b-s)&0xFF for b in c[1:])
# stage B
if not tmp: sys.stdout.buffer.write(b""); raise SystemExit(0)
p=tmp[0];o=bytearray()
for d in tmp[1:]:
    p=(p+d)&0xFF;o.append(p)
sys.stdout.buffer.write(bytes(o))
'''


def enc_l7_pipeline(data: bytes, _: random.Random) -> bytes:
    return base64.b64encode(zlib.compress(data))


def dec_l7_pipeline(comp: bytes) -> bytes:
    return zlib.decompress(base64.b64decode(comp))


SRC_L7_PIPELINE = '''#!/usr/bin/env python3
import base64,zlib,sys
sys.stdout.buffer.write(zlib.decompress(base64.b64decode(sys.stdin.buffer.read())))
'''


# ---------- L8: 混合任务 ----------
def enc_l8_arith_lz(data: bytes, rng: random.Random) -> bytes:
    return enc_l4_arithmetic(enc_l2_lz77(data, rng), rng)


def dec_l8_arith_lz(comp: bytes) -> bytes:
    return dec_l2_lz77(dec_l4_arithmetic(comp))


SRC_L8_ARITH_LZ = '''#!/usr/bin/env python3
import zlib,sys
c=sys.stdin.buffer.read()
if len(c)<3 or c[0]!=0xA1: raise SystemExit(1)
ln=c[1]|(c[2]<<8)
sys.stdout.buffer.write(zlib.decompress(c[3:3+ln]))
'''


def enc_l8_vm_encoding(data: bytes, rng: random.Random) -> bytes:
    vm = enc_l3_stack_vm(data, rng)
    return enc_l1_xor(vm, rng)


def dec_l8_vm_encoding(comp: bytes) -> bytes:
    vm = dec_l1_xor(comp)
    return dec_l3_stack_vm(vm)


SRC_L8_VM_ENCODING = '''#!/usr/bin/env python3
import sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
vm=bytes(b^c[0] for b in c[1:])
st=[];o=bytearray();ip=0
while ip < len(vm):
    op=vm[ip];ip+=1
    if op==0xFF: break
    if op==0x10: st.append(vm[ip]); ip+=1
    elif op==0x20: o.append(st.pop())
    else: raise SystemExit(2)
sys.stdout.buffer.write(bytes(o))
'''


def enc_l8_comp_encrypt(data: bytes, rng: random.Random) -> bytes:
    zipped = bz2.compress(data)
    key = rng.randint(1, 255)
    return bytes([key]) + xor_bytes(zipped, key)


def dec_l8_comp_encrypt(comp: bytes) -> bytes:
    return bz2.decompress(xor_bytes(comp[1:], comp[0]))


SRC_L8_COMP_ENCRYPT = '''#!/usr/bin/env python3
import bz2,sys
c=sys.stdin.buffer.read();
if not c: raise SystemExit(1)
sys.stdout.buffer.write(bz2.decompress(bytes(b^c[0] for b in c[1:])))
'''


TEMPLATES_BY_LEVEL: dict[int, list[Template]] = {
    1: [
        Template("rle", 1, "L1", enc_l1_rle, dec_l1_rle, SRC_L1_RLE),
        Template("base85", 1, "L1", enc_l1_base85, dec_l1_base85, SRC_L1_BASE85),
        Template("xor", 1, "L1", enc_l1_xor, dec_l1_xor, SRC_L1_XOR),
        Template("char_substitution", 1, "L1", enc_l1_char_sub, dec_l1_char_sub, SRC_L1_CHAR_SUB),
    ],
    2: [
        Template("lz77", 2, "L2", enc_l2_lz77, dec_l2_lz77, SRC_L2_LZ77),
        Template("lzss", 2, "L2", enc_l2_lzss, dec_l2_lzss, SRC_L2_LZSS),
        Template("huffman", 2, "L2", enc_l2_huffman, dec_l2_huffman, SRC_L2_HUFF),
        Template("delta", 2, "L2", enc_l2_delta, dec_l2_delta, SRC_L2_DELTA),
        Template("bytecode_interpreter", 2, "L2", enc_l2_bytecode, dec_l2_bytecode, SRC_L2_BYTECODE),
    ],
    3: [
        Template("adaptive_huffman", 3, "L3", enc_l3_adaptive_huffman, dec_l3_adaptive_huffman, SRC_L3_ADAPT_HUFF),
        Template("dictionary_growth_lzw", 3, "L3", enc_l3_lzw_dict, dec_l3_lzw_dict, SRC_L3_LZW),
        Template("stack_vm", 3, "L3", enc_l3_stack_vm, dec_l3_stack_vm, SRC_L3_STACK_VM),
        Template("multi_round_decode", 3, "L3", enc_l3_multi_round, dec_l3_multi_round, SRC_L3_MULTI),
    ],
    4: [
        Template("arithmetic_coding_toy", 4, "L4", enc_l4_arithmetic, dec_l4_arithmetic, SRC_L4_ARITH),
        Template("range_coding_toy", 4, "L4", enc_l4_range, dec_l4_range, SRC_L4_RANGE),
        Template("multi_context_nibble", 4, "L4", enc_l4_multictx, dec_l4_multictx, SRC_L4_MULTICTX),
    ],
    5: [
        Template("dsl_interpreter", 5, "L5", enc_l5_dsl, dec_l5_dsl, SRC_L5_DSL),
        Template("branch_dependent_output", 5, "L5", enc_l5_branch, dec_l5_branch, SRC_L5_BRANCH),
        Template("checksum_structure", 5, "L5", enc_l5_checksum, dec_l5_checksum, SRC_L5_CHECKSUM),
        Template("combinational_logic", 5, "L5", enc_l5_logic, dec_l5_logic, SRC_L5_LOGIC),
    ],
    6: [
        Template("dead_code_injected", 6, "L6", enc_l6_dead_code, dec_l6_dead_code, SRC_L6_DEAD),
        Template("obfuscated_variables", 6, "L6", enc_l6_obf_name, dec_l6_obf_name, SRC_L6_OBF_NAME),
        Template("useless_context", 6, "L6", enc_l6_useless_ctx, dec_l6_useless_ctx, SRC_L6_USELESS),
        Template("misleading_branches", 6, "L6", enc_l6_mislead, dec_l6_mislead, SRC_L6_MISLEAD),
    ],
    7: [
        Template("multi_stage_decode", 7, "L7", enc_l7_multistage, dec_l7_multistage, SRC_L7_MULTISTAGE),
        Template("intermediate_dependency", 7, "L7", enc_l7_intermediate, dec_l7_intermediate, SRC_L7_INTERMEDIATE),
        Template("pipeline_execution", 7, "L7", enc_l7_pipeline, dec_l7_pipeline, SRC_L7_PIPELINE),
    ],
    8: [
        Template("arithmetic_plus_lz", 8, "L8", enc_l8_arith_lz, dec_l8_arith_lz, SRC_L8_ARITH_LZ),
        Template("vm_plus_encoding", 8, "L8", enc_l8_vm_encoding, dec_l8_vm_encoding, SRC_L8_VM_ENCODING),
        Template("compression_plus_encryption", 8, "L8", enc_l8_comp_encrypt, dec_l8_comp_encrypt, SRC_L8_COMP_ENCRYPT),
    ],
}


def split_name(idx: int, total: int) -> str:
    train = int(total * 0.7)
    dev = train + int(total * 0.1)
    if idx < train:
        return "train"
    if idx < dev:
        return "dev"
    return "test"


def materialize_task(task_dir: Path, template: Template, data: bytes, comp: bytes, seed: int, max_size: int) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "decomp.py").write_text(template.decomp_source, encoding="utf-8")
    (task_dir / "data.txt").write_bytes(data)
    meta = {
        "task_id": task_dir.name,
        "level": template.level,
        "type": template.name,
        "family": template.family,
        "max_size": max_size,
        "seed": seed,
        "data_size": len(data),
        "comp_size": len(comp),
    }
    (task_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compute_counts(total: int) -> dict[int, int]:
    if total == 1000:
        return DEFAULT_LEVEL_COUNTS.copy()
    scale = total / 1000
    counts = {k: max(1, round(v * scale)) for k, v in DEFAULT_LEVEL_COUNTS.items()}
    drift = total - sum(counts.values())
    levels = sorted(counts)
    i = 0
    while drift != 0:
        lv = levels[i % len(levels)]
        if drift > 0:
            counts[lv] += 1
            drift -= 1
        elif counts[lv] > 1:
            counts[lv] -= 1
            drift += 1
        i += 1
    return counts


def generate(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = compute_counts(args.total)
    plan: list[Template] = []
    for level, n in counts.items():
        choices = TEMPLATES_BY_LEVEL[level]
        for _ in range(n):
            plan.append(rng.choice(choices))
    rng.shuffle(plan)

    answers_dir = out_dir / "answers"
    if args.save_hidden:
        answers_dir.mkdir(parents=True, exist_ok=True)

    for idx, tpl in enumerate(plan):
        task_id = f"task_{idx:04d}"
        seed = rng.randint(1, 10**9)
        local = random.Random(seed)

        valid = False
        data = b""
        comp = b""
        for _ in range(300):
            data = random_ascii_payload(local)
            # L5 DSL currently 1-byte length field
            if tpl.name == "dsl_interpreter":
                data = data[:255]
            comp = tpl.encode(data, local)
            if len(comp) > args.max_size:
                continue
            try:
                if tpl.decode(comp) == data:
                    valid = True
                    break
            except Exception:
                continue

        if not valid:
            raise RuntimeError(f"cannot generate valid task for {task_id}::{tpl.name}")

        split = split_name(idx, len(plan))
        task_dir = out_dir / split / task_id
        materialize_task(task_dir, tpl, data, comp, seed, args.max_size)
        if args.save_hidden:
            (answers_dir / f"{task_id}.data.comp").write_bytes(comp)

    manifest = {
        "total_tasks": len(plan),
        "seed": args.seed,
        "max_size": args.max_size,
        "splits": {
            "train": int(len(plan) * 0.7),
            "dev": int(len(plan) * 0.1),
            "test": len(plan) - int(len(plan) * 0.7) - int(len(plan) * 0.1),
        },
        "level_counts": counts,
        "template_catalog": {
            str(k): [t.name for t in v] for k, v in TEMPLATES_BY_LEVEL.items()
        },
        "hidden_answers_saved": bool(args.save_hidden),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate InversionBench benchmark tasks")
    p.add_argument("--output", default="benchmark/tasks", help="output directory")
    p.add_argument("--total", type=int, default=1000, help="total task count")
    p.add_argument("--seed", type=int, default=123456, help="global random seed")
    p.add_argument("--max-size", type=int, default=2500, help="max data.comp size")
    p.add_argument("--save-hidden", action="store_true", help="save hidden answers")
    return p.parse_args()


if __name__ == "__main__":
    generate(parse_args())
