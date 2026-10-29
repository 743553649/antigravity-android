#!/usr/bin/env python3
"""
modules/io/interceptors/model_adapter_gateway.py - 移动端内置轻量大模型适配中转网关

【功能说明】
1. 拦截 Antigravity 内核 (Language Server) 的 Cloud Code API 请求：
   - /v1internal:loadCodeAssist (凭证与特性校验)
   - /v1internal:fetchAvailableModels (可用模型列表，注入 DeepSeek / OpenAI / Claude 等)
   - /v1internal:streamGenerateContent (内容生成与流式输出转码)
2. 零外部依赖：纯 Python 原生标准库实现，低内存常驻。
3. 协议双向转码：
   - Google Gemini 协议 <---> OpenAI / Claude 兼容协议。
   - 自动支持函数调用 (Tool Calls)、代码执行、以及 DeepSeek R1 深度思维链 (reasoning_content)。
4. 原生透明回退：如果用户选用原生 Gemini 模型，自动透传回 Google 官方后端。
"""

import os
import sys
import json
import time
import ssl
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Optional

# 默认监听端口（与 antigravity-add-model / IDE 规范保持一致）
DEFAULT_PORT = 50999
CONFIG_FILE_NAME = "custom_models.json"

def get_config_path() -> str:
    """获取自定义模型配置文件路径，优先使用 $HOME/.gemini/antigravity/custom_models.json"""
    home = os.environ.get("HOME", "")
    if not home:
        home = os.path.expanduser("~")
    target_dir = os.path.join(home, ".gemini", "antigravity")
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, CONFIG_FILE_NAME)

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "port": DEFAULT_PORT,
    "upstream_google_url": "https://daily-cloudcode-pa.googleapis.com",
    "providers": {
        "deepseek": {
            "name": "DeepSeek",
            "enabled": True,
            "base_url": "https://api.deepseek.com",
            "api_key": "",
            "models": [
                {
                    "id": "deepseek-chat",
                    "displayName": "DeepSeek V3",
                    "description": "DeepSeek 官方通用代码与对话大模型",
                    "reasoning": False
                },
                {
                    "id": "deepseek-reasoner",
                    "displayName": "DeepSeek R1",
                    "description": "DeepSeek 官方深度推理与长思维链模型",
                    "reasoning": True
                }
            ]
        },
        "openai": {
            "name": "OpenAI",
            "enabled": False,
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "models": [
                {
                    "id": "gpt-4o",
                    "displayName": "GPT-4o",
                    "description": "OpenAI 旗舰全能多模态模型",
                    "reasoning": False
                },
                {
                    "id": "gpt-4o-mini",
                    "displayName": "GPT-4o mini",
                    "description": "OpenAI 高速轻量小模型",
                    "reasoning": False
                }
            ]
        },
        "claude": {
            "name": "Claude (OpenAI 兼容中转/原生)",
            "enabled": False,
            "base_url": "https://api.anthropic.com/v1",
            "api_key": "",
            "models": [
                {
                    "id": "claude-3-5-sonnet-20241022",
                    "displayName": "Claude 3.5 Sonnet",
                    "description": "Anthropic 编程与逻辑最强模型",
                    "reasoning": False
                }
            ]
        },
        "custom": {
            "name": "本地/自定义兼容 (Ollama / OneAPI / NewAPI)",
            "enabled": False,
            "base_url": "http://127.0.0.1:11434/v1",
            "api_key": "",
            "models": [
                {
                    "id": "qwen2.5-coder:7b",
                    "displayName": "Qwen 2.5 Coder",
                    "description": "本地/自建服务商兼容模型",
                    "reasoning": False
                }
            ]
        }
    }
}

class ModelConfigManager:
    """管理模型配置文件的加载、更新与内存缓存"""
    def __init__(self):
        self.config_path = get_config_path()
        self.lock = threading.Lock()
        self.config = self.load()

    def load(self) -> Dict[str, Any]:
        with self.lock:
            if not os.path.isfile(self.config_path):
                try:
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
                    return DEFAULT_CONFIG.copy()
                except Exception as e:
                    print(f"[ModelGateway] 创建默认配置失败: {e}", file=sys.stderr)
                    return DEFAULT_CONFIG.copy()

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                print(f"[ModelGateway] 读取配置失败，采用默认值: {e}", file=sys.stderr)
                return DEFAULT_CONFIG.copy()

    def save(self, new_config: Dict[str, Any]) -> bool:
        with self.lock:
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)
                self.config = new_config
                return True
            except Exception as e:
                print(f"[ModelGateway] 保存配置失败: {e}", file=sys.stderr)
                return False

    def get_model_entry(self, model_id: str) -> Optional[Dict[str, Any]]:
        """根据 model_id 查找对应的服务商与模型配置"""
        clean_id = model_id.replace("models/", "")
        providers = self.config.get("providers", {})
        for p_key, p_val in providers.items():
            if not p_val.get("enabled", False):
                continue
            for m in p_val.get("models", []):
                if m.get("id") == clean_id:
                    return {
                        "provider_key": p_key,
                        "provider_name": p_val.get("name", p_key),
                        "base_url": p_val.get("base_url", ""),
                        "api_key": p_val.get("api_key", ""),
                        "model": m
                    }
        return None

CONFIG_MGR = ModelConfigManager()

def convert_gemini_to_openai(gemini_req: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    """将 Google Gemini 请求格式转换为标准 OpenAI /chat/completions 格式"""
    openai_messages = []

    # 1. 系统提示词 (System Instruction)
    sys_inst = gemini_req.get("systemInstruction")
    if sys_inst:
        parts = sys_inst.get("parts", [])
        sys_text = "".join([p.get("text", "") for p in parts if "text" in p])
        if sys_text:
            openai_messages.append({"role": "system", "content": sys_text})

    # 2. 会话历史与上下文 (Contents)
    for c in gemini_req.get("contents", []):
        role = c.get("role", "user")
        if role == "model":
            role = "assistant"
        parts = c.get("parts", [])

        # 分离纯文本与工具调用
        text_parts = []
        tool_calls = []
        tool_responses = []

        for p in parts:
            if "text" in p:
                text_parts.append(p["text"])
            elif "functionCall" in p:
                fc = p["functionCall"]
                call_id = f"call_{len(tool_calls)}_{int(time.time()*1000)}"
                tool_calls.append({
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": fc.get("name", ""),
                        "arguments": json.dumps(fc.get("args", {}), ensure_ascii=False)
                    }
                })
            elif "functionResponse" in p:
                fr = p["functionResponse"]
                resp_content = fr.get("response", {})
                tool_responses.append({
                    "name": fr.get("name", ""),
                    "content": json.dumps(resp_content, ensure_ascii=False) if isinstance(resp_content, dict) else str(resp_content)
                })

        # 组织 assistant / user / tool 消息
        if tool_calls:
            msg = {"role": "assistant"}
            if text_parts:
                msg["content"] = "".join(text_parts)
            msg["tool_calls"] = tool_calls
            openai_messages.append(msg)
        elif tool_responses:
            for tr in tool_responses:
                openai_messages.append({
                    "role": "tool",
                    "content": tr["content"],
                    "tool_call_id": f"call_{tr['name']}"
                })
        else:
            openai_messages.append({
                "role": role,
                "content": "".join(text_parts) if text_parts else ""
            })

    # 3. 工具与函数定义转换 (Tools / Functions)
    openai_tools = []
    gemini_tools = gemini_req.get("tools", [])
    for gt in gemini_tools:
        for fd in gt.get("functionDeclarations", []):
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": fd.get("name", ""),
                    "description": fd.get("description", ""),
                    "parameters": fd.get("parameters", {"type": "object", "properties": {}})
                }
            })

    out_req: Dict[str, Any] = {
        "model": model_id.replace("models/", ""),
        "messages": openai_messages,
        "stream": True
    }
    if openai_tools:
        out_req["tools"] = openai_tools

    # 4. 生成参数转换
    gen_config = gemini_req.get("generationConfig", {})
    if "temperature" in gen_config:
        out_req["temperature"] = gen_config["temperature"]
    if "maxOutputTokens" in gen_config:
        out_req["max_tokens"] = gen_config["maxOutputTokens"]

    return out_req

class ModelGatewayHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def _set_headers(self, status=200, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-codeium-csrf-token")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        # 1. 状态自检
        if self.path in ("/health", "/status"):
            self._set_headers(200)
            cfg = CONFIG_MGR.config
            active_models = []
            for p_key, p_val in cfg.get("providers", {}).items():
                if p_val.get("enabled", False):
                    for m in p_val.get("models", []):
                        active_models.append(f"{p_key}:{m.get('id')}")
            resp = {
                "ok": True,
                "service": "Antigravity Model Adapter Gateway (Android Native)",
                "active_models": active_models,
                "port": cfg.get("port", DEFAULT_PORT)
            }
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            return

        # 2. 读取配置
        if self.path == "/config":
            self._set_headers(200)
            self.wfile.write(json.dumps(CONFIG_MGR.config, ensure_ascii=False).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(b'{"error": "not found"}')

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        req_json = {}
        if body_bytes:
            try:
                req_json = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                pass

        # 1. 拦截 LoadCodeAssist (告知内核服务可用)
        if "/v1internal:loadCodeAssist" in self.path:
            self._set_headers(200)
            resp = {
                "cloudaicompanionProject": "projects/antigravity-custom",
                "currentTier": "TIER_PRO",
                "allowedTiers": ["TIER_STANDARD", "TIER_PRO"],
                "userStatus": "ACTIVE"
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        # 2. 拦截 FetchAvailableModels (动态注入外接模型列表)
        if "/v1internal:fetchAvailableModels" in self.path:
            self._handle_fetch_available_models(body_bytes)
            return

        # 3. 拦截 StreamGenerateContent (核心大模型生成与流式翻译)
        if "/v1internal:streamGenerateContent" in self.path or "/v1internal:generateContent" in self.path:
            self._handle_generate_content(req_json, body_bytes)
            return

        # 4. 配置修改更新
        if self.path == "/config":
            if req_json and CONFIG_MGR.save(req_json):
                self._set_headers(200)
                self.wfile.write(b'{"ok": true}')
            else:
                self._set_headers(400)
                self.wfile.write(b'{"ok": false, "error": "Invalid config"}')
            return

        # 其他未匹配请求透明回退或返回错误
        self._set_headers(404)
        self.wfile.write(b'{"error": "unknown endpoint"}')

    def _handle_fetch_available_models(self, original_body: bytes):
        """拉取可用模型列表并注入自定义服务商模型"""
        models = [
            {
                "name": "models/gemini-2.5-pro",
                "displayName": "Gemini 2.5 Pro (Default)",
                "description": "Google 官方内置 Gemini 2.5 Pro",
                "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]
            },
            {
                "name": "models/gemini-2.5-flash",
                "displayName": "Gemini 2.5 Flash",
                "description": "Google 官方内置 Gemini 2.5 Flash",
                "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]
            }
        ]

        # 注入用户在 custom_models.json 中启用的所有模型
        cfg = CONFIG_MGR.config
        for p_key, p_val in cfg.get("providers", {}).items():
            if not p_val.get("enabled", False):
                continue
            p_name = p_val.get("name", p_key)
            for m in p_val.get("models", []):
                mid = m.get("id", "")
                mname = m.get("displayName", mid)
                mdesc = m.get("description", f"由 {p_name} 驱动的外接模型")
                models.append({
                    "name": f"models/{mid}",
                    "displayName": f"{mname} ({p_name})",
                    "description": mdesc,
                    "supportedGenerationMethods": ["generateContent", "streamGenerateContent"]
                })

        self._set_headers(200)
        resp_data = {"models": models}
        self.wfile.write(json.dumps(resp_data, ensure_ascii=False).encode("utf-8"))

    def _handle_generate_content(self, req_json: Dict[str, Any], raw_body: bytes):
        """核心处理：根据模型分流并翻译流式响应"""
        requested_model = req_json.get("model", "")
        clean_model_id = requested_model.replace("models/", "")
        model_meta = CONFIG_MGR.get_model_entry(clean_model_id)

        # A. 原生模型或未配置外接模型：透传到 Google 原生后端
        if not model_meta:
            upstream_url = CONFIG_MGR.config.get("upstream_google_url", "https://daily-cloudcode-pa.googleapis.com")
            target_url = upstream_url.rstrip("/") + self.path
            try:
                headers = {}
                for h, v in self.headers.items():
                    if h.lower() not in ("host", "content-length"):
                        headers[h] = v
                req = urllib.request.Request(target_url, data=raw_body, headers=headers, method="POST")
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                return
            except Exception as e:
                self._send_gemini_error(f"连接 Google 原生后端失败: {e}")
                return

        # B. 外接模型：调用对应 OpenAI / DeepSeek / Claude 服务商并进行 SSE 流式双向转码
        api_key = model_meta.get("api_key", "").strip()
        provider_name = model_meta.get("provider_name", "未知服务商")
        provider_key = model_meta.get("provider_key", "custom")
        if not api_key and provider_key != "custom":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            tip_msg = (
                f"【Antigravity 提示】您已选中外接模型，但尚未配置 {provider_name} 的 API 密钥。\n\n"
                f"👉 快速配置方法（在终端执行）：\n"
                f"   agy-models set-key {provider_key} <您的API密钥>\n\n"
                f"配置完成后无需重启，再次发送消息即可直接使用！"
            )
            self._emit_sse({
                "candidates": [{
                    "content": {
                        "parts": [{"text": tip_msg}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }]
            })
            return

        try:
            openai_payload = convert_gemini_to_openai(req_json, clean_model_id)
            base_url = model_meta["base_url"].rstrip("/")
            target_url = f"{base_url}/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}" if api_key else ""
            }

            req_data = json.dumps(openai_payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(target_url, data=req_data, headers=headers, method="POST")

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 开启 Gemini SSE 响应头
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            # 边读外接模型的 SSE 流，边翻译为 Gemini SSE 格式推送给 Antigravity 内核
            accumulated_tool_call: Optional[Dict[str, Any]] = None

            with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})

                            # 1. 普通文本内容
                            content_text = delta.get("content", "")

                            # 2. DeepSeek R1 推理思维链支持 (reasoning_content)
                            reasoning_text = delta.get("reasoning_content", "")
                            if reasoning_text:
                                # 包装为思维链流式展示
                                content_text = reasoning_text

                            if content_text:
                                gemini_chunk = {
                                    "candidates": [{
                                        "content": {
                                            "parts": [{"text": content_text}],
                                            "role": "model"
                                        }
                                    }]
                                }
                                self._emit_sse(gemini_chunk)

                            # 3. 工具调用 (Tool Calls / Function Call)
                            tool_calls = delta.get("tool_calls", [])
                            for tc in tool_calls:
                                fn = tc.get("function", {})
                                fn_name = fn.get("name")
                                fn_args = fn.get("arguments", "")

                                if not accumulated_tool_call:
                                    accumulated_tool_call = {
                                        "name": fn_name or "",
                                        "args_str": fn_args or ""
                                    }
                                else:
                                    if fn_name:
                                        accumulated_tool_call["name"] = fn_name
                                    if fn_args:
                                        accumulated_tool_call["args_str"] += fn_args

                            # 4. 结束判定：若是工具调用结束，则组装完整 functionCall 并发送
                            finish_reason = choices[0].get("finish_reason")
                            if finish_reason == "tool_calls" and accumulated_tool_call:
                                try:
                                    parsed_args = json.loads(accumulated_tool_call["args_str"])
                                except Exception:
                                    parsed_args = {}
                                gemini_fc_chunk = {
                                    "candidates": [{
                                        "content": {
                                            "parts": [{
                                                "functionCall": {
                                                    "name": accumulated_tool_call["name"],
                                                    "args": parsed_args
                                                }
                                            }],
                                            "role": "model"
                                        },
                                        "finishReason": "STOP"
                                    }]
                                }
                                self._emit_sse(gemini_fc_chunk)
                                accumulated_tool_call = None

                        except Exception:
                            continue

            # 发送最后闭合标记
            final_chunk = {
                "candidates": [{
                    "finishReason": "STOP"
                }]
            }
            self._emit_sse(final_chunk)

        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            print(f"[ModelGateway] 服务商 HTTP 异常: {he.code} -> {err_body}", file=sys.stderr)
            self._send_gemini_error(f"外接模型服务商返回错误 (HTTP {he.code}): {err_body}")
        except Exception as e:
            print(f"[ModelGateway] 处理大模型请求异常: {e}", file=sys.stderr)
            self._send_gemini_error(f"外接模型适配网关异常: {e}")

    def _emit_sse(self, data_obj: Dict[str, Any]):
        """向客户端发送 SSE 数据包"""
        try:
            payload = f"data: {json.dumps(data_obj, ensure_ascii=False)}\n\n"
            self.wfile.write(payload.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def _send_gemini_error(self, message: str):
        """向 Antigravity 内核发送友好的 Gemini 错误包"""
        err_chunk = {
            "error": {
                "code": 500,
                "message": message,
                "status": "INTERNAL"
            }
        }
        try:
            self._emit_sse(err_chunk)
        except Exception:
            pass

def run_server(port: int = DEFAULT_PORT):
    """启动本地轻量模型适配中转服务"""
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, ModelGatewayHandler)
    print(f"[ModelGateway] 正在启动 Antigravity 大模型内置中转网关: http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[ModelGateway] 正在关闭网关...")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    p = DEFAULT_PORT
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        p = int(sys.argv[1])
    run_server(p)
