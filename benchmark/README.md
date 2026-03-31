# InversionBench v1 Benchmark 生成器

基于 PRD 的自动任务生成 Pipeline，已覆盖 PRD 中 L1~L8 的**全部示例算法族**。

## 生成结果

```text
benchmark/tasks/
  manifest.json
  train/task_xxxx/{decomp.py,data.txt,meta.json}
  dev/task_xxxx/{decomp.py,data.txt,meta.json}
  test/task_xxxx/{decomp.py,data.txt,meta.json}
  answers/task_xxxx.data.comp   # 仅 --save-hidden 时生成
```

> Agent 可见：`decomp.py` + `data.txt`；
> 隐藏答案：`answers/*.data.comp`（离线评测）。

## 用法

```bash
python3 benchmark/generate_tasks.py \
  --output benchmark/tasks \
  --total 1000 \
  --seed 123456 \
  --max-size 2500 \
  --save-hidden
```

## 参数

- `--output`：输出目录
- `--total`：任务总数（默认 1000）
- `--seed`：随机种子
- `--max-size`：`data.comp` 最大字节数
- `--save-hidden`：保存隐藏答案

## L1~L8 示例算法实现映射

- **L1 无状态变换**：`rle`、`base85`、`xor`、`char_substitution`
- **L2 结构化解码**：`lz77`、`lzss`、`huffman`、`delta`、`bytecode_interpreter`
- **L3 状态型解码**：`adaptive_huffman`、`dictionary_growth_lzw`、`stack_vm`、`multi_round_decode`
- **L4 概率/位级编码**：`arithmetic_coding_toy`、`range_coding_toy`、`multi_context_nibble`
- **L5 程序型反演**：`dsl_interpreter`、`branch_dependent_output`、`checksum_structure`、`combinational_logic`
- **L6 对抗与混淆**：`dead_code_injected`、`obfuscated_variables`、`useless_context`、`misleading_branches`
- **L7 多阶段任务**：`multi_stage_decode`、`intermediate_dependency`、`pipeline_execution`
- **L8 混合任务**：`arithmetic_plus_lz`、`vm_plus_encoding`、`compression_plus_encryption`

## 合法性校验

每个任务自动检查：

1. `comp = encode(data)`
2. `decode(comp) == data`
3. `len(comp) <= max_size`

失败会重采样并重试，确保任务可解。
