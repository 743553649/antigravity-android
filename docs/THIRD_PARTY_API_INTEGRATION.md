# Antigravity Android 接入第三方 API 模型实战全景复盘

> **项目标识**：`com.agy.plus`（Antigravity Android 2.4）  
> **任务目标**：突破 Google 官方额度限制，实现对第三方 OpenAI 兼容 API（以 `https://aiping.cn/api/v1` 及 `DeepSeek-V4.1-Flash-1017` 为基准，兼容 DeepSeek 官方、硅基流动、阿里云百炼、OpenRouter 等）的原生无缝接入。  
> **达成效果**：无需悬浮球与外挂开关，输入栏原生模型选择器直接添加、编辑、切换自定义模型；支持思维链（Thinking）、流式响应（SSE）、工具调用（Tool Calls）及配置连通性即时自检。

---

## 一、 系统整体架构设计

```
[前端交互层 Web UI]
  └─ 输入栏模型选择器 (Ycc / cYb) -> 自定义模型配置弹窗 (Gzb)
  └─ 前端数据仓库 (custom_models_store.js) -> localStorage

[原生桥接层 Android Bridge]
  └─ AndroidBridge.java: saveCustomModels / getCustomModels -> .gemini/custom_models.json
  └─ AndroidBridge.java: testCustomModel -> 实时原生鉴权连通性探测 (绕过 Webview CORS)

[核心语言服务 Language Server]
  └─ language_server (Go 核心引擎) 发起 HTTPS CONNECT 请求

[本地协议转换代理 MITM Proxy]
  └─ LocalModelProxyServer (Port 46159)
       ├─ 官方模型请求 -> 强制 Connection: close 原样透传 Google Cloud
       └─ 自定义模型请求 -> 拦截 cloudcode-pa / generativelanguage:
            1. 解包 Gemini v1internal:streamGenerateContent {"request": {...}}
            2. 协议转换: Contents -> Messages, Tools Schema 清洗 (OpenAI draft-07)
            3. 发送标准 POST /chat/completions (支持 Authorization: Bearer <key>)
            4. 流式转换: delta.reasoning_content / content / tool_calls -> Gemini Candidate SSE
            5. 输出包装: data: {"response": {"candidates": [...]}}
```

---

## 二、 核心修改清单

| 模块 | 修改文件 | 核心变动内容 |
| :--- | :--- | :--- |
| **前端补丁脚本** | `web/patch_main.py` | 1. 解锁 `Ycc` 内的 `linux` 与 `isGoogleInternal` 门控；<br>2. 暴露 `supportsCustomModels` 和 `showCustomModelHeader`；<br>3. 修复 `RXb` 移动端编辑按钮悬停透明（`opacity-0`）问题；<br>4. 重构 `Gzb` 配置弹窗，解决 React `useCallback` 依赖丢失导致的闭包陈旧问题；<br>5. 注入常用服务商预设（AI Ping、DeepSeek、硅基流动等）、密钥明暗切换及连通性测试。 |
| **前端数据管理** | `web/src/patches/custom_models_store.js` | 1. 负责管理 `localStorage` 与 Android 本地存储的双向同步；<br>2. 新增历史配置自愈机制（检测到旧版 DeepSeek 默认 URL 且为 AI Ping 模型时自动纠偏）；<br>3. 增加广播事件 `ag-custom-models-changed`，保持全组件模型列表响应式刷新。 |
| **原生桥接** | `app/src/main/java/com/agy/bridge/AndroidBridge.java` | 1. 增加 `@JavascriptInterface saveCustomModels(json)` 与 `getCustomModels()`；<br>2. 增加 `@JavascriptInterface testCustomModel(url, key, model)`，由原生发起轻量测试，绕过 Webview CORS 限制。 |
| **本地代理** | `app/src/main/java/com/agy/proxy/LocalModelProxyServer.java` | 1. 拆包 `v1internal` 的 `{"request": {...}}` 外层包装；<br>2. 将 Gemini 大写类型 Schema 降级清洗为标准 OpenAI JSON Schema draft-07；<br>3. 支持 `reasoning_content`（深度思考）与流式累加 `tool_calls`；<br>4. 强制透传连接发送 `Connection: close`，防止长连接复用漏掉 MITM；<br>5. 包装 SSE 返回为 `{"response": {"candidates": [...]}}`；<br>6. 报错时输出包含具体 URL 与模型 ID 的直观排错信息。 |

---

## 三、 踩坑记录与排障全景（七大关键坑）

### 坑 1：请求 404 与 Protocol 无法反序列化 (`Agent execution terminated due to error`)
- **现象**：配置模型后发送聊天，立即弹出 `404 Not Found: Requested entity was not found`，对话被强行终止。
- **根因**：
  1. Google 官方内部环境使用 `v1internal:streamGenerateContent` 接口，入参是一个嵌套字典：`{"request": { "contents": [...], "tools": [...] }}`，若直接发给第三方 API 会报非法参数；
  2. Google LS 要求下行 SSE 响应体必须被包裹在 `{"response": {"candidates": [...]}}` 中，缺少 `response` 字段会导致核心的反序列化器无法匹配。
- **解决方案**：
  在 `LocalModelProxyServer.java` 中解构请求体提取真实的 `contents`，并在输出流时统一调用 `wrapResponse(candidate, isV1Internal)` 进行封包。

---

### 坑 2：HTTP Keep-Alive 长连接绕过 MITM 代理
- **现象**：第一句官方对话能通，一切换到自定义模型依然发往 Google，或者自定义模型第一次成功、第二次报 404。
- **根因**：
  HTTP/1.1 默认启用 `Connection: keep-alive`。核心进程在启动后首先向 Google 鉴权接口发起 CONNECT 建立长连接，后续的请求复用了同一条 TLS 通道，导致代理服务器没有收到新的 `CONNECT` 指令，自定义模型判断被直接穿透。
- **解决方案**：
  在代理服务器处理非拦截请求（`passthroughEncryptedSingle`）时，强制将请求头的 `connection` 改写为 `close`，迫使远端和客户端在单次请求完成后立即关闭连接，确保每次聊天都触发全新 CONNECT 握手与 URL 检测。

---

### 坑 3：React 闭包陈旧（Stale Closure）导致 URL 被还原为默认值（HTTP 401 根本原因）
- **现象**：用户在界面中反复确认填入了 `https://aiping.cn/api/v1` 和真实密钥，但每次发送都报：  
  `第三方 API 报错 (HTTP 401): {"error":{"message":"Authentication Fails, Your api key: ****b494 is invalid"}}`  
  经代理抓包发现请求依然被派发到了 `https://api.deepseek.com/v1/chat/completions`。
- **根因**：
  原版组件 `Gzb` 的保存按钮回调使用 `useCallback` 实现：
  ```javascript
  var J = useCallback(() => {
    // 使用了 agBaseUrl 和 agApiKey
  }, [g, k, m, q, t, v, x, c, e, b, B, h]); // 漏掉了 agBaseUrl 和 agApiKey！
  ```
  当用户先输入了模型名称 `k`，React 创建了带有默认 URL（`api.deepseek.com`）的闭包；当用户随后输入了自定义的 `aiping.cn` URL 时，由于依赖项没有 `agBaseUrl`，回调函数并没有被重新生成！点击保存时执行的依然是初始的默认 URL，导致将 AI Ping 密钥发给了 DeepSeek 官方，引发 401 鉴权失败。
- **解决方案**：
  1. 引入 `agFormRef`（`useRef`），保证每次执行回调时均从最新的引用对象中读取输入值；
  2. 在 `useCallback` 依赖数组中完整补齐 `agApiKey`、`agBaseUrl`；
  3. 前端持久层在启动时加入**自愈逻辑**：只要检测到旧版本遗留下来的包含 `1017` 或 `V4` 的模型但其 URL 为旧默认地址，自动修正为 `https://aiping.cn/api/v1`。

---

### 坑 4：移动端触屏下模型列表编辑图标消失
- **现象**：在手机上配好模型后想修改配置，但在下拉列表中找不到「编辑」按钮，只能重新点 `+` 号。
- **根因**：
  原版 UI 为桌面端设计，编辑图标写有 CSS 类名：  
  `className="... opacity-0 transition-opacity group-hover:opacity-100"`  
  移动设备没有鼠标 Hover（悬停）事件，导致编辑按钮始终保持 `opacity-0` 隐形状态。
- **解决方案**：
  在 `web/patch_main.py` 中通过文本正则将 `opacity-0` 替换为 `opacity-80 hover:opacity-100`，使铅笔编辑图标在手机端清晰常驻。

---

### 坑 5：双输入框产生认知歧义（`Model Label` vs `Model URL`）
- **现象**：原生弹窗存在两个名称输入框：`Model Label`（显示名称）和 `Model URL`（原意为 gemini-api scheme 资源路径）。用户很容易将接口地址 `https://aiping.cn/api/v1` 填入 `Model URL`，从而导致参数混乱。
- **解决方案**：
  在配置弹窗中直接合并为唯一的 **`1. 模型 ID (Model ID)`** 输入框（如 `DeepSeek-V4.1-Flash-1017`），并在下方单独划分 **`2. API Base URL`** 与常用平台预设胶囊，前端自动清洗输入，杜绝歧义。

---

### 坑 6：工具调用（Tool Calls）JSON Schema 格式冲突
- **现象**：当聊天请求包含工具（如 `view_file`、`run_command` 等 13 个原生工具）时，部分第三方接口直接返回 `HTTP 400 Bad Request`。
- **根因**：
  Gemini 内部工具定义使用了特定字段（如 `propertyOrdering`、`nullable: true`、大写 `TYPE_STRING` 等），不符合 OpenAI 严格基于 JSON Schema draft-07 的规范。
- **解决方案**：
  在 `LocalModelProxyServer.java` 中编写 `sanitizeJsonSchema()` 递归遍历工具参数，剔除 Google 特有私有字段，将数据类型全部规整为小写规范；若第三方模型依然不支持工具调用返回 400，代理层会自动剥离 tools 进行无工具二次重试（降级重试机制）。

---

### 坑 7：盲测与无反馈闭环
- **现象**：用户填完 Key 和 URL 后，必须退出弹窗、创建新会话、发送一次真实提问才能发现连通性或密钥是否有误，试错成本高。
- **解决方案**：
  在原生层注入 `testCustomModel` 桥接，并在配置弹窗底部增加 **`⚡ 测试连接`** 按钮。点击后由 Android 原生直接发送 1 Token 的轻量探测包，弹窗内即刻高亮展示响应码与诊断信息（`✅ 连接成功 (HTTP 200)` 或 `❌ 鉴权失败 (HTTP 401)`），实现一站式配置验证闭环。

---

## 四、 总结与最佳实践

1. **协议层优先保持干净**：在基于 MITM 的本地反向代理设计中，强制使用 `Connection: close` 是防止长连接串流与规避拦截穿透的核心法门。
2. **移动端交互差异**：桌面 Electron Web 应用移植到移动 Android WebView 时，所有依赖鼠标 `hover` 的操作必须显式转换为常驻按钮或显式交互。
3. **状态管理的原子与兜底**：复杂的第三方配置输入既不能单纯依赖 React 单一闭包（易受渲染时序影响），也不能单纯依赖 localStorage（多端通信不同步），必须建立 `React Ref + localStorage + Native Disk + 启动时自愈校验` 的多级闭环。
