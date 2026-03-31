# InversionBench v1 产品需求文档（PRD）+ Benchmark 自动生成 Pipeline

## 一、项目概述

**项目名称：** InversionBench v1  
**项目定位：** 面向具备工具调用能力的 Agent 的程序反演（Program Inversion）能力评测基准。

### 核心问题形式
给定一个“仅前向执行”的程序 `P`（如解码器）和目标输出 `Y`，要求构造输入 `X`，使得：

```text
P(X) == Y
```

该类问题本质为：
- 程序理解 + 逆向推理
- 状态建模 + 输入构造
- 工程执行（编译 / 调试 / 迭代）

### 核心目标
系统性评测并提升 Agent 在以下能力上的表现：
1. 代码理解能力（C / Python / DSL）
2. 逆向推理能力（decode → encode）
3. 状态推理能力（stateful execution）
4. 输入构造能力（bit-level / structured input）
5. 工具使用能力（编译、运行、调试）

### 非目标
- 不评测纯算法题（如 LeetCode）
- 不依赖外部搜索或知识库
- 不强调自然语言能力

---

## 二、任务定义

### 2.1 标准任务结构

**输入（提供给 Agent）：**
- `/app/decomp.c`（解码程序，或 `.py` / VM）
- `/app/data.txt`（目标输出）

**输出（Agent 需要生成）：**
- `/app/data.comp`

**成功判定：**

```bash
cat data.comp | ./decomp > out.txt
diff out.txt data.txt
```

若完全一致，则任务通过。

### 2.2 约束条件（可配置）

| 参数 | 含义 |
| --- | --- |
| `max_size` | `data.comp` 最大字节数 |
| `time_limit` | 运行时间限制 |
| `memory_limit` | 内存限制 |

默认：`max_size = 2500 bytes`

---

## 三、任务类型体系（扩展版）

为保证 benchmark 覆盖不同能力维度，设计 8 个层级：

### L1：无状态变换（基础）
**目标能力：** 基础程序理解 + 简单构造  
**示例：** RLE 解码、Base 编码（变种 base64/base85）、XOR 编码、字符替换。

### L2：结构化解码
**目标能力：** 结构识别 + 局部逆向  
**示例：** LZ77 / LZSS、Huffman 解码、Delta encoding、简单字节码解释器。

### L3：状态型解码
**目标能力：** 全局状态建模  
**示例：** 自适应 Huffman、字典动态增长、stack VM（带内存）、多轮 decode。

### L4：概率 / 位级编码（核心难点）
**目标能力：** bit-level 控制 + 概率模型  
**示例：** Arithmetic Coding（自适应）、Range Coding、多 context 解码。

### L5：程序型反演（新增）
**目标能力：** 程序逻辑逆推  
**示例：** DSL 解释器、分支依赖输出、checksum 校验结构、组合逻辑构造。

### L6：对抗与混淆（新增）
**目标能力：** 抗干扰理解  
**示例：** 死代码注入、混淆变量名、无用上下文、迷惑性分支。

### L7：多阶段任务（新增）
**目标能力：** 长链路推理  
**示例：** 多阶段 decode、中间文件依赖、pipeline 执行。

### L8：混合任务（高级）
**目标能力：** 综合能力  
**示例：** Arithmetic + LZ、VM + encoding、压缩 + 加密组合。

### 难度控制维度
- 状态依赖程度
- bit-level 精度
- 分支复杂度
- 上下文数量
- 解码深度

---

## 四、数据集规模设计（V1）

总任务数：`1000`

| Level | 数量 |
| --- | ---: |
| L1 | 150 |
| L2 | 150 |
| L3 | 150 |
| L4 | 150 |
| L5 | 150 |
| L6 | 100 |
| L7 | 75 |
| L8 | 75 |

数据划分：
- train: 70%
- dev: 10%
- test: 20%（隐藏）

---

## 五、数据生成 Pipeline（核心）

整体流程：

```text
模板程序 P
↓
数据生成 data.txt
↓
隐藏 encoder
↓
得到 data.comp
↓
自动验证
↓
打包任务
```

### 5.1 模板库设计

目录结构：

```text
templates/
  rle/
  lz77/
  huffman/
  arithmetic/
  vm/
  dsl/
  hybrid/
```

每个模板包含：
- `decomp_template.c`
- `encode_reference.py`（隐藏）
- `config.json`

### 5.2 数据生成（data.txt）
支持模式：
- 随机文本
- JSON / 代码 / 日志
- 高重复数据（LZ）
- 高熵数据（Arithmetic）

示例：

```bash
gen_data.py --size 2000 --mode structured
```

### 5.3 Hidden Encoder
作用：`encode(data.txt) -> data.comp`  
要求：必须合法、必须可解码、不暴露给 agent。

### 5.4 自动验证
执行：

```bash
cat data.comp | ./decomp > out.txt
```

校验：

```bash
diff out.txt data.txt
```

若失败则丢弃任务。

### 5.5 任务打包

```text
task_xxxx/
  decomp.c
  data.txt
  meta.json
```

`meta.json` 示例：

```json
{
  "task_id": "arith_0421",
  "level": 4,
  "type": "arithmetic_lz",
  "max_size": 2500,
  "seed": 123456
}
```

---

## 六、Codex/Agent 自动生成 Pipeline

目标：自动批量生成 1000 个任务。

### 6.1 主生成脚本
`generate_tasks.py` 伪代码：

```python
for template in templates:
    for i in range(num_tasks):
        data = gen_data(template)
        comp = encode(data)
        if validate(comp, data):
            save_task()
```

### 6.2 Agent（Codex）参与点
用于提升多样性：
1. 自动生成 decoder 变体（改变量名、改写循环、插入死代码）
2. 自动生成 encoder（从 decoder 推导）
3. 自动生成 data.txt（多分布）
4. 自动生成对抗版本

### 6.3 自动变异（关键）
每个模板执行：
- rename variables
- add dead branches
- inline functions
- reorder logic

目标：防止模型记忆模板。

### 6.4 随机化参数
例如：`OFF1`、`OFF2`、`LITSIZE`、ctx 数量、概率初始值，保证任务差异性。

---

## 七、评测体系

主指标：`Pass@k`

次指标：
- 输出大小
- 收敛轮数
- 工具调用次数

过程指标：
- 编译成功率
- 运行错误率
- 中间尝试次数

---

## 八、防作弊设计

避免：
- `data.txt` 太短
- trivial identity mapping
- 直接复制输入

措施：
- 模板随机化
- 数据分布随机
- 强制 size 限制

---

## 九、未来扩展（V2）

- 多文件程序
- 部分可观测任务
- 噪声输出
- 在线交互任务
- 自我改进循环

---

## 十、一句话总结

InversionBench 是一个通过“只给前向程序，要求反推输入”的方式，系统性评测 Agent 逆向推理与构造能力的 benchmark。
