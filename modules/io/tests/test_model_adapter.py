#!/usr/bin/env python3
"""
modules/io/tests/test_model_adapter.py - 大模型适配网关单元测试与请求转换验证
"""

import sys
import os
import json
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INTERCEPTORS_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "interceptors")
sys.path.insert(0, INTERCEPTORS_DIR)

from model_adapter_gateway import (
    convert_gemini_to_openai,
    CONFIG_MGR,
    DEFAULT_CONFIG
)

class TestModelAdapterGateway(unittest.TestCase):

    def test_convert_prompt_and_history(self):
        gemini_req = {
            "systemInstruction": {
                "parts": [{"text": "你是安卓开发专家"}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "你好，帮我写一个测试脚本"}]
                },
                {
                    "role": "model",
                    "parts": [{"text": "没问题，这是测试脚本"}]
                },
                {
                    "role": "user",
                    "parts": [{"text": "请继续"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }

        openai_req = convert_gemini_to_openai(gemini_req, "deepseek-chat")

        self.assertEqual(openai_req["model"], "deepseek-chat")
        self.assertTrue(openai_req["stream"])
        self.assertEqual(openai_req["temperature"], 0.7)
        self.assertEqual(openai_req["max_tokens"], 2048)

        messages = openai_req["messages"]
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0], {"role": "system", "content": "你是安卓开发专家"})
        self.assertEqual(messages[1], {"role": "user", "content": "你好，帮我写一个测试脚本"})
        self.assertEqual(messages[2], {"role": "assistant", "content": "没问题，这是测试脚本"})
        self.assertEqual(messages[3], {"role": "user", "content": "请继续"})

    def test_convert_tool_declarations(self):
        gemini_req = {
            "contents": [
                {"role": "user", "parts": [{"text": "查看文件"}]}
            ],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "view_file",
                            "description": "查看本地文件内容",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"}
                                },
                                "required": ["path"]
                            }
                        }
                    ]
                }
            ]
        }

        openai_req = convert_gemini_to_openai(gemini_req, "gpt-4o")
        self.assertIn("tools", openai_req)
        tools = openai_req["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["type"], "function")
        self.assertEqual(tools[0]["function"]["name"], "view_file")
        self.assertEqual(tools[0]["function"]["description"], "查看本地文件内容")

    def test_convert_function_call_and_response(self):
        gemini_req = {
            "contents": [
                {
                    "role": "model",
                    "parts": [
                        {
                            "functionCall": {
                                "name": "run_command",
                                "args": {"CommandLine": "ls -la"}
                            }
                        }
                    ]
                },
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": "run_command",
                                "response": {"output": "file1.txt\nfile2.txt"}
                            }
                        }
                    ]
                }
            ]
        }

        openai_req = convert_gemini_to_openai(gemini_req, "deepseek-reasoner")
        messages = openai_req["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], "run_command")
        self.assertEqual(messages[1]["role"], "tool")
        self.assertIn("file1.txt", messages[1]["content"])

    def test_model_config_loading(self):
        model_entry = CONFIG_MGR.get_model_entry("deepseek-chat")
        self.assertIsNotNone(model_entry)
        self.assertEqual(model_entry["provider_key"], "deepseek")
        self.assertEqual(model_entry["base_url"], "https://api.deepseek.com")

if __name__ == "__main__":
    unittest.main()
