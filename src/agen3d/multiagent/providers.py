"""Hosted VLM and locally authenticated Codex/Claude CLI transports.

No automatic retries: a failed transport may already have incurred a charge.
"""
import base64
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .contracts import Decision, ModelSpec
from .process import run_process


class ProviderHTTPError(RuntimeError):
    """Bounded provider diagnostics, excluding raw headers and response payloads."""

    def __init__(self, status, message):
        self.status = status
        super().__init__(f"HTTP {status}: {message}")


@dataclass
class Reply:
    text: str
    actual_usd: float | None = None
    usage: dict = field(default_factory=dict)
    raw_text: str | None = None


def image_block(path: Path):
    from PIL import Image
    with Image.open(path) as image:
        mime = Image.MIME.get(image.format)
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("Only PNG/JPEG/WebP evidence is supported")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Evidence image exceeds 10 MiB; prepare a bounded crop")
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


class Provider:
    def complete(self, spec: ModelSpec, system: str, packet: dict,
                 images: list[Path], workdir: Path) -> Reply:
        if spec.backend == "mock":
            # Offline control exercises protocol flow, never produces a scientific verdict.
            role = packet["task"]["role"]
            if not packet.get("history"):
                decision = Decision(status="tool", summary="Offline fixture: inspect scene",
                                    calls=[{"name": "read_scene", "arguments": {}}])
            else:
                decision = Decision(status="abstain" if role == "judge" else "done",
                                    summary="Offline fixture only; no model judgment",
                                    uncertainty=["mock backend"])
            return Reply(decision.model_dump_json(), 0, {"mock": True})
        if spec.backend in {"codex", "claude"}:
            return self.cli(spec, system, packet, images, workdir)
        return self.http(spec, system, packet, images)

    def http(self, spec, system, packet, images):
        key = os.environ.get(spec.api_key_env)
        if not key:
            raise RuntimeError(f"Missing environment variable {spec.api_key_env}")
        content = [{"type": "text", "text": json.dumps(packet)}]
        content.extend(image_block(path) for path in images)
        payload = {"model": spec.model,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": content}],
                   "max_tokens": spec.max_output_tokens,
                   "response_format": {"type": "json_object"}, "stream": False}
        for name in ('temperature', 'top_p', 'top_k', 'presence_penalty', 'repetition_penalty', 'seed'):
            value = getattr(spec, name)
            if value is not None:
                payload[name] = value
        schema = packet.get('schema')
        if isinstance(schema, dict) and schema.get('type') == 'object':
            if spec.response_mode == 'schema':
                payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                    'name': schema.get('title', 'response'), 'strict': True, 'schema': schema}}
            content[0]['text'] = 'INPUT CONTEXT ONLY; do not echo this packet.\n' + content[0]['text']
            content.append({'type': 'text', 'text': 'Return a newly computed response matching the response schema. '
                            'Only these top-level keys are permitted: ' + ', '.join(schema.get('properties', {})) +
                            '. Do not copy the input packet or return the schema.'})
        if spec.response_mode == 'text':
            payload.pop('response_format')
            content.append({'type': 'text', 'text': 'Output only the JSON object, without Markdown fences or commentary.'})
        if spec.backend == "openrouter":
            payload["provider"] = {"require_parameters": True, "allow_fallbacks": False}
            if spec.provider:
                payload["provider"]["only"] = [spec.provider]
        request = urllib.request.Request(
            spec.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(request, timeout=spec.timeout_s) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            message = "Provider rejected the request"
            try:
                error = json.loads(exc.read(65536)).get("error", {})
                if isinstance(error, dict) and isinstance(error.get("message"), str):
                    message = error["message"]
                    metadata = error.get("metadata", {})
                    if isinstance(metadata, dict):
                        # Keep only short routing diagnostics, not raw responses or account IDs.
                        details = [f"{field}={metadata[field][:100]}"
                                   for field in ("provider_name", "limit_source")
                                   if isinstance(metadata.get(field), str)]
                        if details:
                            message += " (" + ", ".join(details) + ")"
            except (ValueError, AttributeError):
                pass
            message = message.replace(key, "[redacted]")[:1200]
            raise ProviderHTTPError(exc.code, message) from None
        usage = body.get("usage", {})
        # Provider-reported cost is optional (not zero when missing).
        cost = usage.get("cost")
        choice = body['choices'][0]
        text = choice['message'].get('content')
        if not isinstance(text, str):
            raise ValueError("Provider returned no text decision")
        raw_text = text
        if spec.response_mode == 'text':
            fenced = re.fullmatch(r'\s*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```\s*', text)
            if fenced:
                text = fenced.group(1)
        return Reply(text, float(cost) if cost is not None else None,
                     {"id": body.get("id"), "model": body.get("model"),
                      "provider": body.get("provider"), "usage": usage,
                      'finish_reason': choice.get('finish_reason'),
                      'native_finish_reason': choice.get('native_finish_reason'),
                      'input_tokens': usage.get('prompt_tokens', 0),
                      'output_tokens': usage.get('completion_tokens', 0),
                      'cached_input_tokens': (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0),
                      'json_fence_removed': text != raw_text}, raw_text=raw_text)

    def cli(self, spec, system, packet, images, workdir):
        prompt = system + "\nTASK PACKET\n" + json.dumps(packet)
        # Fresh subprocess/context on every call. Only scheduler executes protocol tool calls.
        with tempfile.TemporaryDirectory(prefix="cli-", dir=workdir) as folder:
            cwd = Path(folder)
            if spec.backend == "codex":
                output = cwd / "decision.json"
                command = ["codex", "exec", "--ignore-user-config", "--ephemeral",
                           "--skip-git-repo-check", "--sandbox", "read-only",
                           "--disable", "shell_tool", "--disable", "unified_exec",
                           "--disable", "multi_agent", "--disable", "multi_agent_v2",
                           "-c", 'web_search="disabled"',
                           "--json", "--output-last-message", str(output)]
                if spec.model:
                    command += ["--model", spec.model]
                if spec.reasoning_effort:
                    command += ["-c", f'model_reasoning_effort="{spec.reasoning_effort}"']
                for path in images:
                    command += ["--image", str(path)]
                command += ["-"]
                result = run_process(command, input=prompt, text=True, cwd=cwd,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     timeout=spec.timeout_s)
                if result.returncode or not output.exists():
                    raise RuntimeError(f"Codex failed (exit {result.returncode}); check CLI login/runtime")
                usage = []
                for line in result.stdout.splitlines():
                    try:
                        event = json.loads(line)
                        if event.get("type") == "turn.completed":
                            usage.append(event.get("usage", {}))
                    except json.JSONDecodeError:
                        continue
                return Reply(output.read_text(), None, {"cli": "codex", "turns": usage})
            command = ["claude", "--print", "--output-format", "stream-json", "--verbose", "--tools", "",
                       "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                       "--disable-slash-commands", "--no-session-persistence",
                       "--permission-mode", "dontAsk", "--setting-sources", ""]
            if spec.model:
                command += ["--model", spec.model]
            # Claude stream-json accepts native image content blocks via stdin.
            command += ["--input-format", "stream-json"]
            content = [{"type": "text", "text": prompt}]
            for path in images:
                block = image_block(path)["image_url"]["url"]
                header, data = block.split(",", 1)
                content.append({"type": "image", "source": {"type": "base64",
                                "media_type": header[5:].split(";")[0], "data": data}})
            message = {"type": "user", "message": {"role": "user", "content": content}}
            result = run_process(command, input=json.dumps(message) + "\n", text=True,
                                 cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 timeout=spec.timeout_s)
            if result.returncode:
                raise RuntimeError(f"Claude failed (exit {result.returncode}); check CLI login/runtime")
            # Streaming input (needed for images) requires streaming output in Claude CLI.
            # Ignore intermediate event types; only its terminal result is a decision.
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            results = [event for event in events if event.get("type") == "result"]
            if not results:
                raise RuntimeError("Claude stream ended without a terminal result")
            body = results[-1]
            if body.get("is_error"):
                raise RuntimeError("Claude reported an error; request may be billed")
            return Reply(body["result"], None,
                         {"cli": "claude", "usage": body.get("usage"),
                          "reported_equivalent_usd": body.get("total_cost_usd")})
