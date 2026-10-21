"""統一的 LLM 介面。依「角色」選供應商，金鑰只從環境變數讀取。

角色：vision / author / student / judge。``mock`` 供應商不連網，回傳固定內容，
讓整條管線在沒有金鑰時也能跑通。
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROLES = ("vision", "author", "student", "judge")


class LLMError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def provider_for(role: str) -> str:
    return (_env(f"GRADER_PROVIDER_{role.upper()}") or _env("GRADER_PROVIDER") or "mock").lower()


def _post(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]  # 錯誤內容不含金鑰
        raise LLMError(f"HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise LLMError(f"請求失敗: {type(exc).__name__}") from exc


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _openai_compat(base: str, key: str, model: str, system: str, user: str,
                   images: Sequence[Path], temperature: float, timeout: float) -> str:
    content: List[Dict[str, Any]] = [{"type": "text", "text": user}]
    for p in images:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{_b64(p)}"}})
    data = _post(f"{base.rstrip('/')}/chat/completions",
                 {"model": model, "temperature": temperature,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": content if images else user}]},
                 {"Authorization": f"Bearer {key}"} if key else {}, timeout)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("回應格式錯誤") from exc


def _anthropic(system: str, user: str, images: Sequence[Path], temperature: float, timeout: float) -> str:
    key = _env("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("缺少 ANTHROPIC_API_KEY")
    content: List[Dict[str, Any]] = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(p)}}
        for p in images]
    content.append({"type": "text", "text": user})
    data = _post("https://api.anthropic.com/v1/messages",
                 {"model": _env("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "max_tokens": 4096,
                  "system": system,  # 新版 Claude 模型已不接受 temperature
                  "messages": [{"role": "user", "content": content}]},
                 {"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout)
    try:
        return "".join(b.get("text", "") for b in data["content"]).strip()
    except (KeyError, TypeError) as exc:
        raise LLMError("回應格式錯誤") from exc


def chat(role: str, system: str, user: str, *, images: Sequence[Path] = (),
         temperature: float = 0.2, timeout: float = 120.0, mock: Optional[str] = None) -> str:
    """回傳文字。``mock`` 是 mock 供應商要回的字串（由呼叫端提供合理預設）。"""
    if role not in ROLES:
        raise ValueError(f"未知角色: {role}")
    prov = provider_for(role)
    if prov == "mock":
        return mock if mock is not None else "{}"
    if prov == "openai":
        key = _env("OPENAI_API_KEY")
        if not key:
            raise LLMError("缺少 OPENAI_API_KEY")
        return _openai_compat(_env("OPENAI_BASE_URL", "https://api.openai.com/v1"), key,
                              _env("OPENAI_MODEL", "gpt-4o-mini"), system, user, images, temperature, timeout)
    if prov == "anthropic":
        return _anthropic(system, user, images, temperature, timeout)
    if prov == "qwen":
        return _openai_compat(_env("QWEN_BASE_URL", "http://localhost:8000/v1"), _env("QWEN_API_KEY"),
                              _env("QWEN_MODEL", "Qwen/Qwen3-30B-A3B"), system, user, images, temperature, timeout)
    raise LLMError(f"不支援的供應商: {prov}")


def parse_json(text: str) -> Any:
    """從 LLM 回應抽出 JSON（容忍 ```json 圍欄與前後說明文字）。"""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise LLMError("回應中找不到 JSON")
    try:
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError as exc:
        raise LLMError("JSON 解析失敗") from exc


def chat_json(role: str, system: str, user: str, *, mock: Any = None, **kw: Any) -> Any:
    raw = chat(role, system, user, mock=json.dumps(mock, ensure_ascii=False) if mock is not None else None, **kw)
    return parse_json(raw)
