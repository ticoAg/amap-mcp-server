"""CLI entrypoints for amap_mcp_server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer

from .mcp_runtime import (
    configure_runtime_settings,
    current_runtime_settings,
    run_server,
    runtime_backend_snapshot,
)
from .server import (
    COMMAND_ACTIONS,
    catalog_snapshot,
    explain_error,
    get_action_help,
    list_command_catalog,
    render_commands_reference_markdown,
    run_command_target,
)

TRANSPORTS = ("stdio", "sse", "streamable-http")

app = typer.Typer(
    add_completion=False,
    help="Amap MCP Server CLI with serve/docs/smoke workflows.",
    no_args_is_help=False,
)
docs_app = typer.Typer(add_completion=False, help="Inspect generated command documentation.")
smoke_app = typer.Typer(add_completion=False, help="Run local smoke checks for command actions.")
app.add_typer(docs_app, name="docs")
app.add_typer(smoke_app, name="smoke")


def _normalize_transport(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in TRANSPORTS:
        raise typer.BadParameter(f"transport must be one of: {', '.join(TRANSPORTS)}")
    return normalized


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _write_output(output: Optional[Path], content: str) -> None:
    if output is None:
        typer.echo(content.rstrip())
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote {output}")


def _render_targets_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Command Catalog", ""]
    if payload.get("ok") is False:
        lines.append(f"- error: {payload.get('error')}")
        for suggestion in payload.get("suggestions", []):
            lines.append(f"- suggestion: {suggestion}")
        return "\n".join(lines)
    level = payload.get("level")
    lines.append(f"- level: `{level}`")
    if "summary" in payload:
        lines.append(f"- summary: {payload['summary']}")
    lines.append("")
    if "commands" in payload:
        for command in payload["commands"]:
            lines.append(f"- `{command}`")
    elif "resources" in payload:
        for resource in payload["resources"]:
            lines.append(f"- `{resource}`")
    elif "actions" in payload:
        for action in payload["actions"]:
            lines.append(f"- `{action['action']}`: {action['summary']}")
    else:
        lines.append(f"## `{payload['target']}`")
        lines.append("")
        lines.append(payload["summary"])
        lines.append("")
        lines.append("参数：")
        for key, description in payload.get("arguments", {}).items():
            lines.append(f"- `{key}`: {description}")
    return "\n".join(lines)


def _render_help_markdown(payload: dict[str, Any]) -> str:
    if payload.get("ok") is False:
        lines = [f"# `{payload.get('target', 'unknown')}`", "", f"- error: {payload.get('error')}"]
        for suggestion in payload.get("suggestions", []):
            lines.append(f"- suggestion: {suggestion}")
        return "\n".join(lines)

    if "field" in payload and "description" in payload:
        lines = [
            f"# `{payload['target']}`",
            "",
            f"## `{payload['field']}`",
            "",
            payload["description"],
            "",
            f"- acceptance: {payload.get('acceptance_hint', '')}",
        ]
        if payload.get("raw_tools"):
            lines.append(f"- raw tools: {', '.join(f'`{tool}`' for tool in payload['raw_tools'])}")
        if payload.get("docs_url"):
            lines.append(f"- docs: {payload['docs_url']}")
        for impl_ref in payload.get("impl_refs", []):
            lines.append(f"- impl: `{impl_ref}`")
        return "\n".join(lines)

    lines = [f"# `{payload['target']}`", "", payload["summary"], "", "适用场景："]
    for use_case in payload.get("use_cases", []):
        lines.append(f"- {use_case}")
    lines.extend(["", "参数："])
    for key, description in payload.get("arguments", {}).items():
        lines.append(f"- `{key}`: {description}")
    lines.extend(["", "示例："])
    for example in payload.get("examples", []):
        lines.append("```json")
        lines.append(json.dumps(example, ensure_ascii=False, indent=2))
        lines.append("```")
    lines.extend(["", "Cites："])
    if payload.get("raw_tools"):
        lines.append(f"- raw tools: {', '.join(f'`{tool}`' for tool in payload['raw_tools'])}")
    if payload.get("docs_url"):
        lines.append(f"- docs: {payload['docs_url']}")
    for impl_ref in payload.get("impl_refs", []):
        lines.append(f"- impl: `{impl_ref}`")
    lines.append(f"- acceptance: {payload.get('acceptance_hint', '')}")
    return "\n".join(lines)


def _parse_args(args_json: Optional[str], args_file: Optional[Path]) -> dict[str, Any]:
    if args_json and args_file:
        raise typer.BadParameter("pass either --args-json or --args-file, not both")
    if args_file is not None:
        return json.loads(args_file.read_text(encoding="utf-8"))
    if args_json:
        return json.loads(args_json)
    return {}


@app.callback(invoke_without_command=True)
def _root_callback(
    ctx: typer.Context,
) -> None:
    """Run the server or delegate to a subcommand."""

    if ctx.invoked_subcommand is not None:
        return
    defaults = current_runtime_settings()
    configure_runtime_settings(
        host=str(defaults["host"]),
        port=int(defaults["port"]),
        mount_path=defaults["mount_path"],
        sse_path=str(defaults["sse_path"]),
        message_path=str(defaults["message_path"]),
        streamable_http_path=str(defaults["streamable_http_path"]),
    )
    run_server(transport="stdio")


def main() -> None:
    """Console script entrypoint."""

    app()


@app.command()
def serve(
    transport: str = typer.Argument("stdio", help="Transport: stdio, sse, or streamable-http."),
    host: str = typer.Option("0.0.0.0", "--host", help="Host for SSE / streamable-http transports."),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Port for SSE / streamable-http transports."),
    mount_path: Optional[str] = typer.Option(None, "--mount-path", help="Optional mount path passed to FastMCP.run()."),
    sse_path: str = typer.Option("/sse", "--sse-path", help="SSE endpoint path."),
    message_path: str = typer.Option("/messages/", "--message-path", help="SSE message endpoint path."),
    streamable_http_path: str = typer.Option("/mcp", "--streamable-http-path", help="Streamable HTTP endpoint path."),
) -> None:
    """Run the MCP server."""

    configure_runtime_settings(
        host=host,
        port=port,
        mount_path=mount_path,
        sse_path=sse_path,
        message_path=message_path,
        streamable_http_path=streamable_http_path,
    )
    run_server(transport=_normalize_transport(transport), mount_path=mount_path)


@docs_app.command("targets")
def docs_targets(
    target: str = typer.Argument("", help="Optional command/resource/action prefix."),
    output_format: str = typer.Option("json", "--format", help="Output format: json or markdown."),
) -> None:
    """List command, resource, or action targets from the catalog."""

    payload = list_command_catalog(target)
    if output_format == "markdown":
        typer.echo(_render_targets_markdown(payload))
        return
    _emit_json(payload)


@docs_app.command("show")
def docs_show(
    target: str = typer.Argument(..., help="Full target in command.resource.action form."),
    field: str = typer.Option("", help="Optional argument field to inspect."),
    output_format: str = typer.Option("json", "--format", help="Output format: json or markdown."),
) -> None:
    """Show detailed help for one target or one argument field."""

    payload = get_action_help(target, field)
    if output_format == "markdown":
        typer.echo(_render_help_markdown(payload))
        return
    _emit_json(payload)


@docs_app.command("export")
def docs_export(
    output_format: str = typer.Option("markdown", "--format", help="Output format: markdown or json."),
    output: Optional[Path] = typer.Option(None, "--output", help="Optional file path to write."),
) -> None:
    """Export the full command catalog."""

    if output_format == "json":
        content = json.dumps(catalog_snapshot(), ensure_ascii=False, indent=2) + "\n"
    elif output_format == "markdown":
        content = render_commands_reference_markdown()
    else:
        raise typer.BadParameter("format must be one of: markdown, json")
    _write_output(output, content)


@docs_app.command("runtime")
def docs_runtime() -> None:
    """Show current MCP runtime backend and settings."""

    _emit_json(runtime_backend_snapshot())


@smoke_app.command("list")
def smoke_list() -> None:
    """List available smoke targets and their default examples."""

    payload = [
        {
            "target": item.target,
            "default_example": item.examples[0] if item.examples else {},
            "acceptance_hint": item.acceptance_hint,
        }
        for item in COMMAND_ACTIONS
    ]
    _emit_json(payload)


@smoke_app.command("run")
def smoke_run(
    target: str = typer.Argument(..., help="Full target in command.resource.action form."),
    args_json: Optional[str] = typer.Option(None, "--args-json", help="Inline JSON args payload."),
    args_file: Optional[Path] = typer.Option(None, "--args-file", help="Path to JSON args payload."),
    example_index: int = typer.Option(0, min=0, help="Use a built-in example when no args are provided."),
) -> None:
    """Execute one command target locally for smoke validation."""

    payload_args = _parse_args(args_json, args_file)
    if not payload_args:
        item = next((entry for entry in COMMAND_ACTIONS if entry.target == target.strip().lower()), None)
        if item is None:
            _emit_json({"ok": False, "target": target, "error": "unknown command target"})
            raise typer.Exit(code=1)
        if example_index >= len(item.examples):
            _emit_json(
                {
                    "ok": False,
                    "target": item.target,
                    "error": f"example index {example_index} out of range",
                    "available_examples": len(item.examples),
                }
            )
            raise typer.Exit(code=1)
        payload_args = dict(item.examples[example_index])
    payload = run_command_target(target, payload_args)
    _emit_json(payload)
    if not payload.get("ok", False):
        raise typer.Exit(code=1)


@smoke_app.command("explain")
def smoke_explain(
    target: str = typer.Argument(..., help="Full target in command.resource.action form."),
    error: str = typer.Argument(..., help="Observed error text."),
) -> None:
    """Explain an observed command error using the same hint logic as MCP."""

    _emit_json(explain_error(target, error))
