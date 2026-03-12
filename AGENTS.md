---
language: zh
type: AI Agent Guidance (Repo-Level)
note: Shared rules for ./amap-mcp-server and its child projects.
---

# amap-mcp-server Repository Guidelines

本文件作用域覆盖 `./amap-mcp-server/**`。

定位：`amap-mcp-server` 是工作区中的高德地图能力仓，负责把 Amap / LBS 能力封装成可被 agent 直接消费的 MCP tool。

## 1. 开始工作前先看什么

进入本仓库时，默认按以下顺序阅读：

1. `./AGENTS.md`
2. `./README.md`
3. `./pyproject.toml`
4. `./amap_mcp_server/server.py`

说明：

- 父级 `AGENTS.md` 的作用域会自动生效，不需要在仓库级 `AGENTS.md` 中显式回跳引用。
- 跨仓协作机制统一以工作区根目录的 `AGENTS.md` / `workflow.md` 为准，本文件只补充本仓特有信息。

## 2. 仓库职责

- 封装高德地图 API 为 MCP tools
- 收口 geocode / regeocode / weather / POI / routing 等能力
- 为上层 agent 场景提供稳定的参数与返回结构
- 在需要时，从 raw Amap API 往更适合 agent 的能力面逐步演进

## 3. 本仓工作重点

- 高德具体能力、参数收口、错误处理、返回结构优先在本仓实现。
- 当前代码入口以 [server.py](/Users/ticoag/Documents/myws/clawers/workspace/amap-mcp-server/amap_mcp_server/server.py) 为主。
- 如需更高层命令面或更适合 agent 的封装，可以在本仓继续演进，但尽量保持现有稳定 tool 名清晰可追踪。

## 4. 最小验证

- 可先用 `AMAP_MAPS_API_KEY=... uv run --project . python -c "import amap_mcp_server.server"` 做最小 import 验证。
- 如果改了具体工具，补一条对应的可复现调用命令即可。
