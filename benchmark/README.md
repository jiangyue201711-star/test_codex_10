# InversionBench v1 Benchmark 生成器

本目录提供基于 PRD 的自动任务生成 Pipeline。

## 产物结构

运行生成脚本后输出：

```text
benchmark/tasks/
  manifest.json
  train/task_xxxx/{decomp.py,data.txt,meta.json}
  dev/task_xxxx/{decomp.py,data.txt,meta.json}
  test/task_xxxx/{decomp.py,data.txt,meta.json}
  answers/task_xxxx.data.comp   # 仅 --save-hidden 时生成
```

任务面向 Agent 的输入为 `decomp.py` 与 `data.txt`，目标是构造 `data.comp`。
`answers/` 目录是隐藏答案（离线评测用），默认不写出。

## 使用方法

```bash
python3 benchmark/generate_tasks.py --output benchmark/tasks --total 1000 --seed 123456 --max-size 2500 --save-hidden
```

### 参数

- `--output`：输出目录（默认 `benchmark/tasks`）
- `--total`：任务总数（默认 `1000`）
- `--seed`：随机种子（默认 `123456`）
- `--max-size`：`data.comp` 大小限制（默认 `2500`）
- `--save-hidden`：保存隐藏答案 `answers/*.data.comp`

## 覆盖层级

脚本按照 PRD 的 V1 比例构造 8 个层级：

- L1: xor
- L2: rle
- L3: stateful delta
- L4: nibble context
- L5: checksum frame
- L6: obfuscated xor
- L7: multi-stage (rle + xor)
- L8: hybrid (delta + nibble)

## 校验逻辑

每个任务生成时都执行：

1. `comp = encode(data)`
2. `decode(comp) == data`
3. `len(comp) <= max_size`

不满足则重采样，确保任务合法可解。
