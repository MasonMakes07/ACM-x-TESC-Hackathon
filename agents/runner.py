"""Generic agent loop: Grok may call tools, then must return schema-valid JSON.

Owner: Person 2 (Grok Agent Intelligence).
"""

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from agents.agent_errors import AgentOutputError
from agents.toolbox import AgentToolbox
from schemas.assessment import ProgressEvent

ModelT = TypeVar("ModelT", bound=BaseModel)
ProgressCallback = Callable[[ProgressEvent], None]

MAX_TOOL_ROUNDS = 4
ERROR_PREVIEW_CHARS = 1500


# =============================================================================
# ChatClient
# =============================================================================

# Anything with a Grok-style chat() method (the real client or a test fake).
class ChatClient(Protocol):
    # Sends messages and optional tools, returning the assistant message dict.
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...


# Sends one real progress event to the dashboard.
def emit(on_progress: ProgressCallback, agent_name: str, message: str) -> None:
    on_progress(
        ProgressEvent(
            timestamp=datetime.now(timezone.utc), agent=agent_name, message=message
        )
    )


# Extracts the outermost JSON object from a reply, tolerating fences and prose.
def extract_json(content: str | None) -> str:
    text = (content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if 0 <= start < end else text


# Builds the instruction telling the model exactly which JSON schema to return.
def _format_instructions(output_model: type[BaseModel]) -> str:
    schema = json.dumps(output_model.model_json_schema(), separators=(",", ":"))
    return (
        "\n\nWhen you have finished using tools, reply with ONE JSON object only "
        "(no prose, no code fences) matching this JSON Schema:\n" + schema
    )


# Returns the status field of a tool result string for progress messages.
def _tool_status(tool_result: str) -> str:
    try:
        return str(json.loads(tool_result).get("status", "unknown"))
    except (ValueError, AttributeError):
        return "unknown"


# Runs one agent: lets Grok call tools, then validates its final JSON answer.
def run_agent(
    client: ChatClient,
    *,
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    output_model: type[ModelT],
    on_progress: ProgressCallback,
    toolbox: AgentToolbox | None = None,
    tool_names: tuple[str, ...] = (),
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
) -> ModelT:
    tools = toolbox.definitions(tool_names) if toolbox and tool_names else None
    system_content = system_prompt + _format_instructions(output_model)
    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_prompt},
    ]
    reply: dict = {}
    for round_index in range(max_tool_rounds + 1):
        round_tools = tools if round_index < max_tool_rounds else None
        reply = client.chat(messages, tools=round_tools)
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls or round_tools is None or toolbox is None:
            break
        messages.append(
            {
                "role": "assistant",
                "content": reply.get("content") or "",
                "tool_calls": tool_calls,
            }
        )
        for call in tool_calls:
            function = call.get("function") or {}
            tool_name = str(function.get("name", ""))
            tool_result = toolbox.execute(tool_name, function.get("arguments"))
            emit(on_progress, agent_name, f"{tool_name}: {_tool_status(tool_result)}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(call.get("id", "")),
                    "content": tool_result,
                }
            )

    content = reply.get("content") or ""
    try:
        return output_model.model_validate_json(extract_json(content))
    except ValidationError as error:
        emit(on_progress, agent_name, "Output failed validation; requesting a fix.")
        messages += [
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": (
                    "That reply did not match the required schema. Errors:\n"
                    f"{str(error)[:ERROR_PREVIEW_CHARS]}\n"
                    "Reply again with the corrected JSON object only."
                ),
            },
        ]
    repaired_content = client.chat(messages).get("content") or ""
    try:
        return output_model.model_validate_json(extract_json(repaired_content))
    except ValidationError as error:
        raise AgentOutputError(
            f"{agent_name} returned invalid structured output twice."
        ) from error
