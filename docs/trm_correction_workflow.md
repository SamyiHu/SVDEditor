# TRM 提取人工纠错工作流

## 路径与启动

- `SVDEditor` 根目录即当前工作区根目录。
- 外部解析器优先尝试同级 `../Parser`，也支持 `SVDEDITOR_PARSER_PATH` 显式指定。
- `reg_core` 只在真正解析时惰性加载；Parser 缺失时编辑器主体仍可启动。
- 开工前保留两个工程的未提交修改，不执行 `commit`/`push`。

## 链路

1. `ParserBridge.parse_sync()` 调用 `reg_core.TrmWordParser`，并收集 `last_mismatches`、`last_errors`、`last_warnings`、`last_issues`、`diagnostics`。
   - 机器结果先写入按内容哈希命名、不可覆盖的 `*.snapshot-<hash>.json`。
   - 人工接受/拒绝/忽略/修改写入追加式 `*.events.jsonl` 事件账本。
   - `*.resolved-model.json` 保存机器快照 + 人工 Overlay 合并后的最终模型。
2. 解析结果转换为字段级 `CorrectionRecord`，每个记录保存：
   - `extracted_value` / `original_extracted_value`
   - `manual_value` / `final_value`
   - `modified_at`、`note`
   - 来源文件与 SHA-256
   - 章节、小节、标题、表格序号、行号、原文片段
   - 稳定对象 ID、语义路径、别名、匹配理由、匹配分数
   - 来源权威度、解析完整度、多源一致度、人工状态
3. 记录写入来源旁的 `*.svd-corrections.json` sidecar；同一 TRM 重新解析时按稳定 key 自动重放人工确认值。
4. `ChipToSvdConverter` 使用最终值生成 SVD；`SVDVerifier` 对当前 SVD 做外设/寄存器/位域三层核对。
5. `*.manifest.json` 记录来源/快照/事件/Resolved Model/最终 SVD/报告的 SHA-256、审核统计和未解决风险。

## 可编辑审阅页

`工具 -> 从数据手册导入 -> 预览解析结果 -> 可编辑纠错` 支持：

- 修改外设名、基址、描述；寄存器名、偏移、复位值、访问类型、描述；位域名、bit offset、bit width、访问类型、描述。
- 直接输入人工值，不要求接受系统建议。
- 单行接受、单行拒绝、批量接受、批量忽略、撤销。
- 默认按“差异优先（待核实）”筛选，也可筛选人工值有改动、高风险字段、多源冲突。
- 查看解析值 / 人工值 / 最终值，以及来源权威度 / 解析完整度 / 多源一致度 / 人工状态。
- 查看稳定对象 ID、匹配理由和匹配分数，确认名称匹配不是静默猜测。
- 点击来源定位查看原文片段；Word 来源会尝试用 Word Find 定位，失败时打开原 TRM。
- 导出最终 SVD、Markdown/JSON 纠错报告和交付 Manifest。

核对面板继续保留接受差异、全部接受错误、Markdown 报告、重新核对和跳转能力，并支持人工值、拒绝/忽略建议和来源定位。

## 置信度语义

四列严格分开，均不解释为准确率：

- **来源权威度**：TRM/结构化辅助资料/派生资料类型。
- **解析完整度**：字段齐全程度（complete/partial/incomplete）。
- **多源一致度**：single_source/consistent/conflict。
- **人工确认状态**：机器提取、人工确认、人工拒绝、已忽略、待核实。

原有机器置信度只用于排序和筛选。

## 名称归一化

寄存器核对先精确匹配，再做模板匹配和同外设前缀匹配：

- `ADC + ADC_STS` 对 `STS`
- `CRC + CRC_CON` 对 `CON`
- `UART0 + UART0_CON` 对 `CON`
- 不跨外设把 `ADC_STS` 与 `CRC_STS` 混为一项。

## 验证命令

项目 `.venv` 已安装 `pytest`/`pytest-qt`。由于 Windows 沙箱禁止 pytest 使用系统 Temp，数据源测试使用 `-p no:tmpdir -p no:pytest-qt`：

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider -p no:tmpdir -p no:pytest-qt `
  tests\test_datasource_core.py tests\test_datasource_integration.py tests\test_datasource_corrections.py -q
```

Parser TRM 测试：

```powershell
..\\Parser\\.venv\\Scripts\\python.exe -m pytest -p no:cacheprovider `
  tests\test_trm_parser.py tests\test_trm_word_parser.py tests\test_generators.py -q
```

真实样例回归和 Qt 离屏检查：

```powershell
.venv\Scripts\python.exe tools\run_real_sc32f10t_regression.py
$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python.exe tools\run_offscreen_ui_check.py
```

真实样例固定为：

- `../CDB整合/外发资料/外发资料/31.ARM+C51合并上官网/SVD文件/SC32F10T_10G_Technical_Reference_Manual v0.2cn.docx`
- 同目录 `SC32F10XSX44.svd`

输出落在 `test_data/SC32F10T_10G_regression/`，包括 sidecar、最终 SVD、Markdown/JSON 纠错报告和回归 JSON。

## 中断生成

- `TrmWordParser` 识别“中断向量 / 中断号 / 优先级 / 向量地址 / 中断源”表。
- 系统异常保留在审计模型中；CMSIS-SVD `<interrupt>` 只写 NVIC IRQ（`irq_number >= 0`）。
- `INT1-7` 归一化为 `INT1_7`，`UART0/UART2` 合并为 `UART0_2`，并保留原始别名。
- 生成 SVD 时将 INT 系列中断关联到 `INT`/`INTF` 外设，避免中断只存在于顶层数据而不出现在 SVD。

## 账本和可复现性

- 解析快照按内容哈希去重，不由人工编辑或重新解析覆盖。
- 人工操作以 JSONL 追加 `event_id/transaction_id/object_id/source_anchor`。
- 同一 TRM 重解析后按对象身份与来源锚点重放 Overlay；机器临时记录自动清理，人工记录保留。
- 最终 SVD 不是审计边界，Manifest 才把输入、Overlay、输出和未解决风险绑定在一起。

## 已知边界

- Word 原文定位依赖本机 Word COM；没有 Word 时回退为打开 TRM 文件。
- 多源融合仍沿用现有 `SourceFusion` 与冲突审阅面板；sidecar 主键以主 TRM 来源定位为主。
- `base_address`、版本、封装和实例化模板差异仍会在核对报告中显示，需人工判断，不能用来源权重自动当作准确率。
