# TODOS.md — 技术债务和计划

## P1 — 高优先级

### 首次设置向导
- **What**: 新用户打开后的引导流程（选引擎 → 输 Key → 扫码）
- **Why**: 降低普通用户门槛，当前直接进检测页无任何引导
- **Effort**: S (CC: ~15min)
- **Status**: CEO review accepted，待实施

### main_window.py 拆分
- **What**: 1400+ 行单文件拆分为 qr_view.py / dashboard.py / settings.py / files_view.py
- **Why**: 单文件过大，难以维护
- **Effort**: S (CC: ~15min)

## P2 — 中优先级

### PyInstaller 打包
- **What**: 打包成单文件 .exe，普通用户双击即用
- **Why**: 消除 Python 安装门槛
- **Effort**: L (CC: ~30min)

### 操作历史持久化
- **What**: AI 操作记录保存到磁盘，重启后可查看
- **Why**: 用户关闭窗口后操作记录丢失
- **Effort**: M (CC: ~20min)

### 多语言 README 同步
- **What**: 更新 docs/i18n/ 下 9 种语言的 README 反映新定位
- **Why**: 当前多语言 README 描述的还是旧版 JS CLI
- **Effort**: S (CC: ~15min)

## P3 — 低优先级

### 本地模型支持（Ollama）
- **What**: 通过 Open Interpreter + Ollama 支持完全离线运行
- **Why**: 部分用户对数据隐私有要求
- **Effort**: M

### macOS / Linux 支持
- **What**: 测试并适配非 Windows 平台
- **Why**: 扩大用户群
- **Effort**: L

### 插件生态
- **What**: 允许用户自定义 adapters 和工具
- **Why**: 长期扩展性
- **Effort**: XL
