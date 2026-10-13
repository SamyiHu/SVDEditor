# SVDEditor MCP 集成设计 — AI 能力从「内嵌」走向「MCP」

> 状态：设计稿（待评审实施） · 日期：2026-10-13
>
> 一句话总结：**SVDEditor 不再内嵌 LLM 调用与聊天 UI，改为提供一个标准 MCP Server，
> 让用户已有的 AI 客户端（ZCode / Claude Desktop / Cursor / Cherry Studio / Cline 等）
> 接入即可完成 SVD 编辑与可视化。**

---

## 1. 背景与动机

内嵌 AI 助手（`svd_tool/ai_assistant/`）的维护痛点：

| 痛点 | 说明 |
|------|------|
| 协议耦合 | `backend.py` 直连 OpenAI / Anthropic API，模型厂商一换协议/换模型就要改代码 |
| UI 负担 | 聊天面板、气泡、设置对话框……聊天体验做不过专业客户端，却是纯负担 |
| 用户错位 | 用这个工具的人大多已有顺手的 AI 软件，只想「接入」，不想再配一份 API key |

MCP（Model Context Protocol）恰好解决这三点：

- **协议归 MCP SDK 管**：工具定义写一份，协议升级交给 `mcp` 官方 SDK；
- **UI 归 AI 客户端管**：SVDEditor 只暴露能力，不做对话界面；
- **模型归用户管**：用户在自己喜欢的客户端里用任意模型（云端/本地 Ollama 均可）。

---

## 2. 现有资产盘点（为什么改造成本低）

关键洞察：**`ai_assistant/command_executor.py` 已经是一套完整的「工具层」**，
MCP 化的本质只是把它最外层的「传输端」换掉：

```
现在：内嵌聊天 UI ──OpenAI/Anthropic function-calling──► command_executor._op_*()
之后：外部 AI 客户端 ──MCP(stdio)──► svd-editor-mcp ──┬─ headless: core/* 直接操作
                                                     └─ bridge:  转发 action JSON 给 GUI
```

可直接复用的资产：

| 资产 | 位置 | 复用方式 |
|------|------|----------|
| 33 个操作的完整实现（增删改查/校验/对比/多文档/数据手册） | `command_executor.py` 的 `_operation_map` | 语义照抄为 MCP tool |
| action JSON 协议 `{"operation", "params"}` → `{"success", "message", "data"}` | `CommandExecutor.execute()` | Bridge 模式线协议原样使用 |
| 主线程串行化（BlockingQueuedConnection，与手动操作互斥防竞态） | `command_executor.py` `_GuiBridge` | Bridge 模式直接继承安全性 |
| 撤销集成（每个写操作都有 undo_fn，进 Ctrl+Z 栈） | `_execute_undoable()` | Bridge 模式下 AI 的修改可被用户撤销 |
| 轻量上下文摘要 + 分层获取信息架构（info → get_peripheral → get_register → get_field） | `prompt_builder.py` | 抄进各 MCP tool 的 description，控 token |
| 文件级全部能力（parse/generate/validate/diff/merge/export/header/conflicts/CRUD） | `core/*` + `cli.py` 19 个命令 | Headless 模式的实现基座 |

**设计原则：不发明新概念。MCP 工具 = 现有操作换个名字暴露，行为、参数、返回与 GUI/CLI 完全一致。**

---

## 3. 双模式架构

```
┌──────────────────┐  MCP (stdio / streamable-http)  ┌─────────────────────────┐
│  AI 客户端        │ ◄─────────────────────────────► │  svd-editor-mcp          │
│  ZCode / Claude  │                                 │  (独立 Python 进程)       │
│  Desktop / Cursor│                                 └───────────┬─────────────┘
└──────────────────┘                                             │ 启动时探测 bridge.json
                                                    ┌────────────┴────────────┐
                                                    ▼                         ▼
                                          ┌──────────────────┐    ┌──────────────────────┐
                                          │  Headless 模式    │    │  Bridge 模式          │
                                          │  （默认）         │    │  （GUI 正在运行时）    │
                                          │                  │    │                      │
                                          │ 内存多文档工作区   │    │ TCP 127.0.0.1 + token │
                                          │ 复用 core/*      │    │ action JSON 转发到     │
                                          │ 无 PyQt 依赖     │    │ GUI CommandExecutor   │
                                          │ 编辑→save 才落盘  │    │ 实时刷新/可撤销/可截图  │
                                          └──────────────────┘    └──────────────────────┘
```

### 3.1 Headless 模式（默认）

- Server 进程内维护工作区：`{doc_id: DeviceInfo}`，`open_svd` 解析入内存，`save_document` 才写盘（写前自动 `.bak`）。
- 全部走 `svd_tool.core`，**不 import PyQt**，无显示环境 / CI / 容器里都能跑。
- 适合：脚本化批量任务、Cursor 里改文件、CI 校验。

### 3.2 Bridge 模式（GUI 联动，可视化的关键）

- GUI 增加菜单开关：**工具 → AI 桥接服务（MCP）**，开启后主窗口起 `QTcpServer` 监听 `127.0.0.1` 随机端口（零新增依赖），并把 `{port, token, pid}` 写入 `%APPDATA%/SVDEditor/bridge.json`，退出时删除。
- MCP server 每次工具调用前探测该文件 + 端口连通性：有效则把 action JSON 原样转发给 GUI 的 `CommandExecutor.execute()`，无效则回落 Headless。
- **工具名和语义两种模式完全一致，AI 客户端无感知**——区别只在「改的是内存文件还是活 GUI」。
- Bridge 独有能力（Headless 下调用则返回提示）：
  - `gui_screenshot(target)` —— 树 / 位域图 / 地址图截图，以 **MCP image content（base64 PNG）** 返回，多模态客户端直接「看到」结果并自我校对；
  - `gui_focus(peripheral[, register, field])` —— 复用现有 `jump` 操作，在 GUI 里高亮定位（AI 改完 → 用户视线被带到改动处）。
- AI 的所有写操作进 GUI 撤销栈（现有 `_execute_undoable` 机制），用户 Ctrl+Z 即可整体回退 AI 的操作。

### 3.3 模式探测规则

```
1. 读 %APPDATA%/SVDEditor/bridge.json（不存在 → Headless）
2. 校验 pid 存活 + TCP 连通 + token 握手（失败 → 删失效文件，回落 Headless）
3. 会话期间保持长连接；GUI 退出后自动降级 Headless，已打开文档在 server 侧以文件为准重新挂载
```

---

## 4. 桥接通道细节（GUI ↔ MCP Server）

| 项 | 设计 | 理由 |
|----|------|------|
| 传输 | TCP，仅绑定 `127.0.0.1`，随机端口 | QTcpServer 零依赖；named pipe 跨 Qt/Python 手写帧太别扭 |
| 鉴权 | 首帧携带 token（bridge.json 中的随机串），不符即断开 | 防本机其他进程误接/越权 |
| 线协议 | 按行 JSON：`{"id":…, "operation":…, "params":{…}}` → `{"id":…, "success":…, "message":…, "data":…}` | 与 `CommandExecutor.execute()` 签名一一对应，GUI 侧十几行胶水 |
| 并发 | 单连接即可满足；GUI 侧靠现有主线程派发串行化 | 与手动操作天然互斥，无新增竞态 |
| 生命周期 | GUI 关闭 → server 降级；server 退出 → GUI 检测断开自动关闭监听 | 双向干净退出 |

---

## 5. MCP 工具清单（v1）

命名统一 `svd_` 前缀（客户端里多 server 共存时一眼可辨）。数量控制在 **≈30 个**，
参数 schema 直接照抄 `_op_*` 的 params 约定（地址/偏移用十六进制字符串，如 `"0x40000000"`）。

### 会话与文档
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_open(path)` → doc_id | `_op_open_document` / CLI 无 |
| `svd_list_documents` | `_get_open_documents_info` |
| `svd_switch_document(doc_id)` | `_op_switch_document` |
| `svd_save_document(doc_id?, path?)` | `_op_save_document` |
| `svd_device_info(doc_id?)` | `_op_info`（轻量摘要：设备 + 统计 + 外设名列表） |

### 查询（分层获取，控 token）
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_search(query)` | `_op_search`（统一语法 `type: name: addr:`） |
| `svd_get_peripheral(name)` | `_op_get_peripheral` |
| `svd_get_register(peripheral, name)` | `_op_get_register` |
| `svd_get_field(peripheral, register, field)` | `_op_get_field`（含枚举值） |
| `svd_list_interrupts` | `_op_list_interrupts` |

### 编辑（CRUD × 三级 + 设备 + 中断）
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_update_device(props)` | `_op_update_device` |
| `svd_add_peripheral` / `svd_update_peripheral` / `svd_remove_peripheral` | 同名 `_op_*` |
| `svd_add_register` / `svd_update_register` / `svd_remove_register` | 同名 `_op_*` |
| `svd_add_field` / `svd_update_field` / `svd_remove_field` | 同名 `_op_*` |
| `svd_add_interrupt` / `svd_update_interrupt` / `svd_remove_interrupt` | 同名 `_op_*` |

### 校验与对比
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_validate(doc_id?, strict?)` | `_op_validate` |
| `svd_conflicts(doc_id?)` | `_op_conflicts` |
| `svd_diff(doc_a, doc_b, peripheral?)` | `_op_diff` / `_op_diff_peripheral` |

### 输出
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_export(format: csv/markdown/html, out?)` | `svd_exporter` |
| `svd_generate_header(out?, style?, prefix?)` | `header_generator` |
| `svd_regenerate_xml(doc_id?)` → XML 文本 | `svd_generator`（AI 可直接读标准化 XML） |

### 数据手册（Phase 3，依赖懒加载）
| MCP tool | 对应现有实现 |
|----------|--------------|
| `svd_parse_datasheet(sources[], strategy?)` | `_op_parse_datasheet` |
| `svd_import_to_svd(mode: new/merge)` | `_op_import_to_svd` |
| `svd_verify_against_datasheet` | `_op_verify_against_datasheet` |

### GUI 专属（仅 Bridge 模式）
| MCP tool | 说明 |
|----------|------|
| `svd_gui_screenshot(target: tree/bitfield/address_map)` | image content 返回 |
| `svd_gui_focus(peripheral[, register, field])` | 复用 `_op_jump` |

### MCP Resources / Prompts（加分项）
- **resources**：每个打开的文档注册 `svd://doc/<name>`（完整 XML，按需拉取，避免塞进对话）；
- **prompts**：内置常用工作流模板——「从数据手册生成 SVD」「手册核对与修复」「地址冲突清理」。

---

## 6. 包结构与依赖

```
svd_tool/
├── mcp_server/                # 新增：MCP Server（独立可选组件，不进 GUI 依赖）
│   ├── __init__.py
│   ├── __main__.py            # python -m svd_tool.mcp_server
│   ├── server.py              # FastMCP 入口：tool 注册、模式探测
│   ├── headless_workspace.py  # 文件级工作区（open/save/多文档），只 import core/*
│   ├── bridge_client.py       # TCP + token 客户端，action JSON 转发
│   └── tools_*.py             # 工具定义按组分文件（tools_query/tools_edit/...）
├── ui/...
│   └── managers/
│       └── mcp_bridge.py      # 新增：GUI 侧 QTcpServer 桥（Phase 2）
└── ai_assistant/              # Phase 4 起逐步退役（见 §8）
```

- 依赖隔离：新增 `requirements-mcp.txt`（`mcp>=1.x`），或 setup.py extras：`pip install svd-editor[mcp]`。**不装也不影响 GUI/CLI**。
- 分发入口：console_script `svd-editor-mcp`；同时支持 `python run.py --mcp`（源码用户零安装心智）。

---

## 7. 客户端接入（用户视角：三行配置）

标准 `mcpServers` 格式，各客户端通用（Claude Desktop / Cursor / ZCode / Cherry Studio / Cline）：

```json
{
  "mcpServers": {
    "svd-editor": {
      "command": "svd-editor-mcp",
      "env": { "PYTHONUTF8": "1" }
    }
  }
}
```

源码用户：

```json
{
  "mcpServers": {
    "svd-editor": {
      "command": "python",
      "args": ["C:/path/to/SVDEditor/run.py", "--mcp"],
      "env": { "PYTHONUTF8": "1" }
    }
  }
}
```

Windows 注意事项：
- 必须设 `PYTHONUTF8=1`（stdio 中文输出防乱码）；
- Claude Desktop 需用绝对 `python.exe` 路径（已知 `cmd /c` 包装问题）；
- uv 用户可用 `uv run --project <repo> svd-editor-mcp`。

---

## 8. 内嵌 AI 的去留

| 组件 | 处置 |
|------|------|
| `backend.py`（OpenAI/Anthropic 直连） | **删除**——这是「协议换了要改」的根源 |
| `chat_panel.py` / `chat_bubble.py` / `settings_dialog.py`（聊天 UI） | **删除**——UI 负担 |
| `config.py`（API key 管理） | 删除（不再存任何密钥） |
| `chat_history.py` | 删除（对话历史归 AI 客户端） |
| `command_executor.py` | **保留**：Bridge 模式的服务端；Phase 4 将其中纯数据逻辑下沉到 `core/operations/`，与 Headless 工作区共用一份实现 |
| `prompt_builder.py` | 文案并入各 MCP tool description 后删除 |
| README「AI Assistant」章节 | 改写为「AI 集成（MCP）」：能力不变，接入方式从配 API key 变为三行 MCP 配置 |

---

## 9. 实施路线（每阶段独立可用、独立发版）

### Phase 1 — Headless MVP（先行，价值最大）
- `mcp_server/` + `headless_workspace.py`：会话/查询/编辑/校验/输出五组工具（约 25 个）；
- `run.py --mcp` + `requirements-mcp.txt` + `svd-editor-mcp` 入口；
- README 增补「AI 集成（MCP）」章节（此时内嵌助手暂留）；
- **验收**：Cursor/ZCode 里接上，打开 SVD → 查询 → 改寄存器 → save → validate 全链路通。

### Phase 2 — GUI 桥（编辑可视化闭环）
- GUI 侧 `mcp_bridge.py`（QTcpServer + token + 菜单开关 + 状态栏指示）；
- server 侧 `bridge_client.py` + 模式探测 + `svd_gui_screenshot` / `svd_gui_focus`；
- **验收**：AI 在 Bridge 模式改位域 → GUI 实时刷新 → 截图回给模型 → 模型自查位宽正确 → 用户 Ctrl+Z 可撤销。

### Phase 3 — 数据手册三件套上 MCP
- `svd_parse_datasheet` / `svd_import_to_svd` / `svd_verify_against_datasheet`；
- 重依赖（openpyxl/python-docx/pdfplumber 等）懒加载，未装时工具返回安装指引；
- **验收**：纯 AI 客户端内完成「手册 → SVD → 核对 → 修复」全流程。

### Phase 4 — 退役内嵌 AI、收口
- 删 `backend/chat_*/settings_dialog/config/prompt_builder`，操作层下沉 `core/operations/`；
- README AI 章节定稿、`ai_assistant.png` 截图替换为 MCP 接入示意图；
- requirements 清理，发 **v1.3.0**（Breaking：移除内置 AI 面板）。

---

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| 工具列表太长，客户端上下文吃紧 | 分阶段注册；description 精炼并复用「分层获取」引导（先 info 再逐级 get） |
| 大 SVD 文件 token 爆炸 | 查询一律返回裁剪片段；完整 XML 走 resource 按需拉；沿用轻量摘要策略 |
| mcp SDK 演进破坏兼容 | extras 钉住 minor 版本；CI 加一条「起 server 列工具」冒烟测试 |
| AI 误改文件 | Headless 编辑只进内存、save 显式落盘且自动 `.bak`；Bridge 模式全部可撤销 |
| 桥被本机其他进程滥用 | 仅 loopback + 随机 token + pid 校验，GUI 退出即失效 |
| 双模式行为不一致 | 同一套操作名与参数约定，工具层单测覆盖两种后端（headless/bridge fake） |
| Windows 编码/路径问题 | 强制 `PYTHONUTF8=1`；文档给绝对路径配置范例 |

---

## 11. 总结

- **用户侧体验**：装一次、配三行，任何 MCP 客户端 + 任意模型即可编辑 SVD、看位域图截图、跑手册核对；
- **维护侧收益**：删掉 API 后端与聊天 UI（约占 ai_assistant 一半代码），协议/模型/UI 三类变化全部与本项目解耦；
- **实现侧优势**：工具层（33 个操作）、撤销、线程安全、信息分层架构全部现成，MCP 只做「换传输端」。
