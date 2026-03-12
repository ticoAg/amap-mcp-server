"""MCP runtime adapter for registering Amap tools.

This module intentionally isolates the MCP runtime wiring from the Amap
command surface and business logic. When the official MCP Python SDK v2
runtime becomes directly consumable in this workspace, the migration should
localize primarily to this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .server import FACADE_TOOL_FUNCTIONS, RAW_TOOL_FUNCTIONS

ToolFn = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class RuntimeTransportSettings:
    """Transport-facing settings shared by runtime adapters."""

    host: str = "127.0.0.1"
    port: int = 8000
    mount_path: str | None = "/"
    sse_path: str = "/sse"
    message_path: str = "/messages/"
    streamable_http_path: str = "/mcp"


class RuntimeAdapter(ABC):
    """Stable runtime interface that future MCP v2 adapters should implement."""

    backend_name: str
    migration_phase: str

    @abstractmethod
    def configure(self, settings: RuntimeTransportSettings) -> None:
        """Apply transport settings to the current runtime."""

    @abstractmethod
    def current_settings(self) -> RuntimeTransportSettings:
        """Return current transport settings."""

    @abstractmethod
    def run(self, *, transport: str, mount_path: str | None = None) -> None:
        """Run the MCP server."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return design-oriented runtime state for docs and acceptance."""


class FastMCPRuntimeAdapter(RuntimeAdapter):
    """Current runtime adapter backed by FastMCP.

    This class is intentionally the only place that knows about FastMCP. The
    rest of the repo should speak to the `RuntimeAdapter` interface instead.
    """

    backend_name = "fastmcp-v1-compat-adapter"
    migration_phase = "v2-ready"

    def __init__(
        self,
        *,
        server_name: str,
        raw_tools: tuple[ToolFn, ...],
        facade_tools: tuple[ToolFn, ...],
    ) -> None:
        self._raw_tools = raw_tools
        self._facade_tools = facade_tools
        self._mcp = FastMCP(server_name)
        for tool_fn in (*raw_tools, *facade_tools):
            self._mcp.tool()(tool_fn)

    def configure(self, settings: RuntimeTransportSettings) -> None:
        self._mcp.settings.host = settings.host
        self._mcp.settings.port = settings.port
        if settings.mount_path is not None:
            self._mcp.settings.mount_path = settings.mount_path
        self._mcp.settings.sse_path = settings.sse_path
        self._mcp.settings.message_path = settings.message_path
        self._mcp.settings.streamable_http_path = settings.streamable_http_path

    def current_settings(self) -> RuntimeTransportSettings:
        return RuntimeTransportSettings(
            host=self._mcp.settings.host,
            port=self._mcp.settings.port,
            mount_path=self._mcp.settings.mount_path,
            sse_path=self._mcp.settings.sse_path,
            message_path=self._mcp.settings.message_path,
            streamable_http_path=self._mcp.settings.streamable_http_path,
        )

    def run(self, *, transport: str, mount_path: str | None = None) -> None:
        self._mcp.run(transport=transport, mount_path=mount_path)

    def snapshot(self) -> dict[str, Any]:
        return {
            "runtime_backend": self.backend_name,
            "runtime_phase": self.migration_phase,
            "adapter_class": self.__class__.__name__,
            "registered_raw_tools": len(self._raw_tools),
            "registered_facade_tools": len(self._facade_tools),
            "settings": asdict(self.current_settings()),
        }


def build_runtime_adapter() -> RuntimeAdapter:
    """Build the current runtime adapter.

    Future MCP Python SDK v2 adoption should primarily change this factory.
    """

    return FastMCPRuntimeAdapter(
        server_name="amap-maps",
        raw_tools=RAW_TOOL_FUNCTIONS,
        facade_tools=FACADE_TOOL_FUNCTIONS,
    )


runtime_adapter: RuntimeAdapter = build_runtime_adapter()


def configure_runtime_settings(
    *,
    host: str,
    port: int,
    mount_path: str | None,
    sse_path: str,
    message_path: str,
    streamable_http_path: str,
) -> None:
    """Apply transport-facing settings to the current runtime adapter."""

    runtime_adapter.configure(
        RuntimeTransportSettings(
            host=host,
            port=port,
            mount_path=mount_path,
            sse_path=sse_path,
            message_path=message_path,
            streamable_http_path=streamable_http_path,
        )
    )


def current_runtime_settings() -> dict[str, Any]:
    """Expose current transport settings for CLI defaults."""

    return asdict(runtime_adapter.current_settings())


def runtime_backend_snapshot() -> dict[str, Any]:
    """Expose design-oriented runtime state for docs and acceptance."""

    return runtime_adapter.snapshot()


def run_server(*, transport: str, mount_path: str | None = None) -> None:
    """Run the currently selected runtime adapter."""

    runtime_adapter.run(transport=transport, mount_path=mount_path)
