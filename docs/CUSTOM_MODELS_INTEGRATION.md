# Antigravity 外接大模型支持指南 (DeepSeek / OpenAI / Claude)

本项目成功将社区项目 `vahapogut/antigravity-add-model` 与 `lbjlaq/Antigravity-Tools-LS` 的大模型外接转换逻辑移植至 Android ARM64 原生环境。

---

## 1. 架构设计与移植原理

### 为什么不能直接搬照电脑端程序？
* **电脑端原理**：在电脑后台常驻运行独立的代理中转程序（如 Node.js / Electron 或 Rust 编译的 `.exe`），拦截 Antigravity 发往 Google 的 API 请求。
* **安卓端痛点**：安卓手机拥有极为严苛的进程管理机制，独立后台常驻进程极易被手机系统省电策略查杀（OOM Killer）。
* **我们的移动端原生方案**：
  1. **应用进程内嵌中转网关**：将协议转换器（`model_adapter_gateway.py`）作为 App 前台服务（`CoreServerService`）的内置常驻守护子服务，随 Antigravity 一同启动与休眠，零额外内存负担，绝不被手机系统杀后台。
  2. **内置 ConnectRPC 重定向**：利用 Antigravity 核心原生的 `LanguageServerService/SetCloudCodeURL` 接口，在前端初始化时（`web/src/core/fetch-rewrite.js`）自动将内核网络请求无感重定向至本地网关 `http://127.0.0.1:50999`。
  3. **双向协议转换**：
     - Google Gemini 协议与 OpenAI / Claude 协议互转。
     - 完整支持**自主写代码、编辑文件、执行命令**等 Agent 工具调用（Tool / Function Call）。
     - 支持 **DeepSeek R1 深度思考/长思维链**（`reasoning_content`）流式回显。
     - **原生透明回退**：选用官方 Gemini 模型时，自动透传至 Google 官方后端，零侵入性。

---

## 2. 快速使用指南

### 查看当前模型与状态
在终端执行：
```bash
agy-models list
```
检查本地网关运行状态：
```bash
agy-models status
```

---

### 配置 API 密钥

#### 1. 配置 DeepSeek (推荐，性价比与代码能力极高)
```bash
agy-models set-key deepseek sk-xxxxxxxxxxxxxxxxxxxxxxxx
```
> 配置后自动启用 DeepSeek V3 (`deepseek-chat`) 与 DeepSeek R1 (`deepseek-reasoner`)。

#### 2. 配置 OpenAI
```bash
agy-models set-key openai sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

#### 3. 配置 Claude (或第三方中转站)
```bash
agy-models set-key claude sk-xxxxxxxxxxxxxxxxxxxxxxxx
# 如果使用第三方 OpenAI 兼容中转站：
agy-models set-url claude https://your-relay-api.com/v1
```

#### 4. 配置本地 Ollama / 自建服务商
```bash
agy-models enable custom
agy-models set-url custom http://127.0.0.1:11434/v1
```

---

## 3. 在界面中选择模型

配置好 Key 后，**无需重启应用**：
1. 打开 Antigravity 手机界面。
2. 点击输入框上方的**模型选择器**。
3. 下拉列表中将直接出现：
   - `DeepSeek V3 (DeepSeek)`
   - `DeepSeek R1 (DeepSeek)`
   - `GPT-4o (OpenAI)`
   - `Claude 3.5 Sonnet (Claude)`
4. 选中后即可像内置模型一样正常对话、让 AI 自动阅读项目代码、修改文件与执行测试。

---

## 4. 配置文件位置

所有服务商与模型配置持久化保存在：
```text
~/.gemini/antigravity/custom_models.json
```
可通过手动修改该 JSON 文件自由增删更多自定义模型。
