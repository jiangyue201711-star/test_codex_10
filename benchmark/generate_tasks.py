#!/usr/bin/env python3
"""InversionBench v1 benchmark generation pipeline.

Generates tasks with this structure:
  split/task_xxxx/
    decomp.py
    data.txt
    meta.json

Optional hidden answers:
  answers/task_xxxx.data.comp
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


DEFAULT_LEVEL_COUNTS = {
    1: 150,
    2: 150,
    3: 150,
    4: 150,
    5: 150,
    6: 100,
    7: 75,
    8: 75,
}


def random_ascii_payload(rng: random.Random, min_len: int = 48, max_len: int = 220) -> bytes:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-,.[]{}() \n"
    size = rng.randint(min_len, max_len)
    return "".join(rng.choice(alphabet) for _ in range(size)).encode("utf-8")


@dataclass
class Template:
    name: str
    level: int
    encode: Callable[[bytes, random.Random], bytes]
    decode: Callable[[bytes], bytes]
    decomp_source: Callable[[dict], str]


def t1_encode(data: bytes, rng: random.Random) -> bytes:
    key = rng.randint(1, 255)
    return bytes([key]) + bytes(b ^ key for b in data)


def t1_decode(comp: bytes) -> bytes:
    key = comp[0]
    return bytes(b ^ key for b in comp[1:])


def t1_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def main():
    comp = sys.stdin.buffer.read()
    if not comp:
        return
    key = comp[0]
    out = bytes([b ^ key for b in comp[1:]])
    sys.stdout.buffer.write(out)

if __name__ == "__main__":
    main()
'''


def t2_encode(data: bytes, _: random.Random) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        run = 1
        while i + run < len(data) and data[i + run] == data[i] and run < 255:
            run += 1
        out.extend([run, data[i]])
        i += run
    return bytes(out)


def t2_decode(comp: bytes) -> bytes:
    if len(comp) % 2 != 0:
        raise ValueError("bad rle")
    out = bytearray()
    for i in range(0, len(comp), 2):
        out.extend([comp[i + 1]] * comp[i])
    return bytes(out)


def t2_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def main():
    comp = sys.stdin.buffer.read()
    if len(comp) % 2 != 0:
        raise SystemExit(1)
    out = bytearray()
    for i in range(0, len(comp), 2):
        out.extend([comp[i + 1]] * comp[i])
    sys.stdout.buffer.write(bytes(out))

if __name__ == "__main__":
    main()
'''


def t3_encode(data: bytes, rng: random.Random) -> bytes:
    seed = rng.randint(0, 255)
    prev = seed
    out = bytearray([seed])
    for b in data:
        c = (b - prev) & 0xFF
        out.append(c)
        prev = (prev + c) & 0xFF
    return bytes(out)


def t3_decode(comp: bytes) -> bytes:
    prev = comp[0]
    out = bytearray()
    for c in comp[1:]:
        prev = (prev + c) & 0xFF
        out.append(prev)
    return bytes(out)


def t3_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def main():
    comp = sys.stdin.buffer.read()
    if not comp:
        return
    prev = comp[0]
    out = bytearray()
    for c in comp[1:]:
        prev = (prev + c) & 0xFF
        out.append(prev)
    sys.stdout.buffer.write(bytes(out))

if __name__ == "__main__":
    main()
'''


def t4_encode(data: bytes, rng: random.Random) -> bytes:
    # bit-level packing: store each byte as two nibbles with context xor
    key = rng.randint(1, 15)
    out = bytearray([key])
    for i, b in enumerate(data):
        hi = ((b >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((b & 0xF) ^ ((key + i * 3) & 0xF)) & 0xF
        out.append((hi << 4) | lo)
    return bytes(out)


def t4_decode(comp: bytes) -> bytes:
    key = comp[0]
    out = bytearray()
    for i, x in enumerate(comp[1:]):
        hi = ((x >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((x & 0xF) ^ ((key + i * 3) & 0xF)) & 0xF
        out.append((hi << 4) | lo)
    return bytes(out)


def t4_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def main():
    comp = sys.stdin.buffer.read()
    if not comp:
        return
    key = comp[0]
    out = bytearray()
    for i, x in enumerate(comp[1:]):
        hi = ((x >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((x & 0xF) ^ ((key + i * 3) & 0xF)) & 0xF
        out.append((hi << 4) | lo)
    sys.stdout.buffer.write(bytes(out))

if __name__ == "__main__":
    main()
'''


def t5_encode(data: bytes, rng: random.Random) -> bytes:
    salt = rng.randint(1, 255)
    chk = (sum(data) + salt) & 0xFF
    return bytes([salt, chk]) + data


def t5_decode(comp: bytes) -> bytes:
    salt, chk = comp[0], comp[1]
    data = comp[2:]
    if ((sum(data) + salt) & 0xFF) != chk:
        raise ValueError("checksum mismatch")
    return data


def t5_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def main():
    comp = sys.stdin.buffer.read()
    if len(comp) < 2:
        raise SystemExit(1)
    salt, chk = comp[0], comp[1]
    data = comp[2:]
    if ((sum(data) + salt) & 0xFF) != chk:
        raise SystemExit(2)
    sys.stdout.buffer.write(data)

if __name__ == "__main__":
    main()
'''


def t6_encode(data: bytes, rng: random.Random) -> bytes:
    # same core as xor, but with dead bytes to emulate obfuscation
    key = rng.randint(1, 255)
    noise = rng.randint(0, 255)
    out = bytes(((b ^ key) ^ (noise & 0)) for b in data)
    return bytes([noise, key]) + out


def t6_decode(comp: bytes) -> bytes:
    key = comp[1]
    return bytes(b ^ key for b in comp[2:])


def t6_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def dead_branch(x):
    if (x * 7 + 3) % 2 == 999999:
        return x ^ 123
    return x

def main():
    comp = sys.stdin.buffer.read()
    if len(comp) < 2:
        return
    key = comp[1]
    out = bytearray()
    for b in comp[2:]:
        t = dead_branch(b)
        out.append((t ^ key) ^ (0 & comp[0]))
    sys.stdout.buffer.write(bytes(out))

if __name__ == "__main__":
    main()
'''


def t7_encode(data: bytes, rng: random.Random) -> bytes:
    # stage1 rle -> stage2 xor
    s1 = t2_encode(data, rng)
    key = rng.randint(1, 255)
    s2 = bytes(b ^ key for b in s1)
    return bytes([key]) + s2


def t7_decode(comp: bytes) -> bytes:
    key = comp[0]
    s1 = bytes(b ^ key for b in comp[1:])
    return t2_decode(s1)


def t7_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def rle_decode(comp):
    if len(comp) % 2 != 0:
        raise SystemExit(1)
    out = bytearray()
    for i in range(0, len(comp), 2):
        out.extend([comp[i + 1]] * comp[i])
    return bytes(out)

def main():
    comp = sys.stdin.buffer.read()
    if not comp:
        return
    key = comp[0]
    stage = bytes([b ^ key for b in comp[1:]])
    sys.stdout.buffer.write(rle_decode(stage))

if __name__ == "__main__":
    main()
'''


def t8_encode(data: bytes, rng: random.Random) -> bytes:
    # hybrid: stateful delta then nibble obfuscation
    s1 = t3_encode(data, rng)
    key = rng.randint(1, 15)
    out = bytearray([key])
    for i, b in enumerate(s1):
        out.append((((b >> 4) ^ ((key + i) & 0xF)) << 4) | (((b & 0xF) ^ ((key + i * 5) & 0xF))))
    return bytes(out)


def t8_decode(comp: bytes) -> bytes:
    key = comp[0]
    s1 = bytearray()
    for i, x in enumerate(comp[1:]):
        hi = ((x >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((x & 0xF) ^ ((key + i * 5) & 0xF)) & 0xF
        s1.append((hi << 4) | lo)
    return t3_decode(bytes(s1))


def t8_source(_: dict) -> str:
    return '''#!/usr/bin/env python3
import sys

def delta_decode(comp):
    prev = comp[0]
    out = bytearray()
    for c in comp[1:]:
        prev = (prev + c) & 0xFF
        out.append(prev)
    return bytes(out)

def main():
    comp = sys.stdin.buffer.read()
    if len(comp) < 2:
        return
    key = comp[0]
    stage = bytearray()
    for i, x in enumerate(comp[1:]):
        hi = ((x >> 4) ^ ((key + i) & 0xF)) & 0xF
        lo = ((x & 0xF) ^ ((key + i * 5) & 0xF)) & 0xF
        stage.append((hi << 4) | lo)
    sys.stdout.buffer.write(delta_decode(bytes(stage)))

if __name__ == "__main__":
    main()
'''


TEMPLATES = [
    Template("xor", 1, t1_encode, t1_decode, t1_source),
    Template("rle", 2, t2_encode, t2_decode, t2_source),
    Template("state_delta", 3, t3_encode, t3_decode, t3_source),
    Template("nibble_ctx", 4, t4_encode, t4_decode, t4_source),
    Template("checksum_frame", 5, t5_encode, t5_decode, t5_source),
    Template("obf_xor", 6, t6_encode, t6_decode, t6_source),
    Template("pipeline_rle_xor", 7, t7_encode, t7_decode, t7_source),
    Template("hybrid_delta_nibble", 8, t8_encode, t8_decode, t8_source),
]


def split_name(index: int, total: int) -> str:
    train_cut = int(total * 0.7)
    dev_cut = train_cut + int(total * 0.1)
    if index < train_cut:
        return "train"
    if index < dev_cut:
        return "dev"
    return "test"


def materialize_task(task_dir: Path, template: Template, data: bytes, comp: bytes, seed: int, max_size: int) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "decomp.py").write_text(template.decomp_source({}), encoding="utf-8")
    (task_dir / "data.txt").write_bytes(data)
    meta = {
        "task_id": task_dir.name,
        "level": template.level,
        "type": template.name,
        "max_size": max_size,
        "seed": seed,
        "data_size": len(data),
        "comp_size": len(comp),
    }
    (task_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def generate(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    counts = DEFAULT_LEVEL_COUNTS.copy()
    if args.total != 1000:
        scale = args.total / 1000
        counts = {k: max(1, round(v * scale)) for k, v in counts.items()}
        # adjust rounding drift
        diff = args.total - sum(counts.values())
        keys = sorted(counts)
        i = 0
        while diff != 0:
            k = keys[i % len(keys)]
            if diff > 0:
                counts[k] += 1
                diff -= 1
            elif counts[k] > 1:
                counts[k] -= 1
                diff += 1
            i += 1

    plan = []
    for tpl in TEMPLATES:
        plan.extend([tpl] * counts[tpl.level])
    rng.shuffle(plan)

    answers_dir = out_dir / "answers"
    if args.save_hidden:
        answers_dir.mkdir(exist_ok=True)

    for idx, tpl in enumerate(plan):
        task_id = f"task_{idx:04d}"
        seed = rng.randint(1, 10**9)
        local_rng = random.Random(seed)

        for _ in range(200):
            data = random_ascii_payload(local_rng)
            comp = tpl.encode(data, local_rng)
            if len(comp) > args.max_size:
                continue
            if tpl.decode(comp) == data:
                break
        else:
            raise RuntimeError(f"failed to generate valid sample for {task_id} ({tpl.name})")

        split = split_name(idx, len(plan))
        task_dir = out_dir / split / task_id
        materialize_task(task_dir, tpl, data, comp, seed, args.max_size)

        if args.save_hidden:
            (answers_dir / f"{task_id}.data.comp").write_bytes(comp)

    summary = {
        "total_tasks": len(plan),
        "max_size": args.max_size,
        "seed": args.seed,
        "splits": {
            "train": int(len(plan) * 0.7),
            "dev": int(len(plan) * 0.1),
            "test": len(plan) - int(len(plan) * 0.7) - int(len(plan) * 0.1),
        },
        "level_counts": counts,
        "templates": [{"name": t.name, "level": t.level} for t in TEMPLATES],
        "hidden_answers_saved": bool(args.save_hidden),
    }
    (out_dir / "manifest.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate InversionBench benchmark tasks")
    p.add_argument("--output", default="benchmark/tasks", help="output directory")
    p.add_argument("--total", type=int, default=1000, help="total task count")
    p.add_argument("--seed", type=int, default=123456, help="global random seed")
    p.add_argument("--max-size", type=int, default=2500, help="max compressed input size")
    p.add_argument("--save-hidden", action="store_true", help="store hidden data.comp files")
    return p.parse_args()


if __name__ == "__main__":
    generate(parse_args())
