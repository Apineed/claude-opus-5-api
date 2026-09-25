"""
Single-file lightweight Python client for APINEED Claude Opus 5.
Requires: pip install requests
"""

import json
import os
from typing import Any, Dict, Generator, List, Optional, Union
import requests


class ApineedError(Exception):
    """Base exception for APINEED API errors."""
    pass


class ClaudeOpus5Client:
    """
    Claude Opus 5 Client powered by APINEED.
    
    Compatible with OpenAI-standard chat completion format with zero heavy dependencies.
    Model ID: anthropic/claude-opus-5
    """

    DEFAULT_MODEL = "anthropic/claude-opus-5"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://apineed.com/v1",
        timeout: int = 120,
    ):
        self.api_key = api_key or os.getenv("APINEED_API_KEY")
        if not self.api_key:
            raise ValueError(
                "APINEED API Key is required. Pass it via ClaudeOpus5Client(api_key='...') "
                "or set the APINEED_API_KEY environment variable. "
                "Get one at https://apineed.com/models/claude-opus-5"
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ClaudeOpus5Client/1.0",
        })

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        response_format: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        **extra_kwargs,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to Claude Opus 5.
        
        :param messages: List of message dicts: [{"role": "user", "content": "..."}]
        :param model: Target model name (defaults to anthropic/claude-opus-5)
        :param temperature: Sampling temperature (0.0 to 2.0)
        :param max_tokens: Maximum number of tokens to generate
        :param response_format: e.g. {"type": "json_object"} for structured outputs
        :return: Standard OpenAI-compatible response dict
        """
        payload: Dict[str, Any] = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if top_p is not None:
            payload["top_p"] = top_p
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        payload.update(extra_kwargs)

        res = self._session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=self.timeout,
        )
        if not res.ok:
            raise ApineedError(
                f"ClaudeOpus5Client.chat failed [{res.status_code}]: {res.text}"
            )
        return res.json()

    def stream_chat(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **extra_kwargs,
    ) -> Generator[str, None, None]:
        """
        Stream chat responses token-by-token via Server-Sent Events (SSE).
        
        Usage:
            for chunk in client.stream_chat("Explain quantum physics"):
                print(chunk, end="", flush=True)
        """
        if isinstance(messages, str):
            msg_list = []
            if system_prompt:
                msg_list.append({"role": "system", "content": system_prompt})
            msg_list.append({"role": "user", "content": messages})
        else:
            msg_list = messages

        payload: Dict[str, Any] = {
            "model": model or self.DEFAULT_MODEL,
            "messages": msg_list,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(extra_kwargs)

        res = self._session.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            stream=True,
            timeout=self.timeout,
        )
        if not res.ok:
            raise ApineedError(
                f"ClaudeOpus5Client.stream_chat failed [{res.status_code}]: {res.text}"
            )

        for line in res.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_str = line_str[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    def ask(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Convenience method for single-turn text question and answer."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.chat(messages=messages, model=model, **kwargs)
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ApineedError(f"Unexpected response structure: {response}")

    def chat_with_vision(
        self,
        prompt: str,
        image_url: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Send a multimodal prompt containing text and an image URL."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        })
        response = self.chat(messages=messages, **kwargs)
        return response["choices"][0]["message"]["content"]

