# Acceptance

这里记录 `amap-mcp-server` 当前推荐的最小验收闭环。目标不是跑全量线上集成，而是快速证明：

1. command catalog 可被发现
2. 帮助信息与 reference 文档一致
3. smoke 命令可以复用 catalog 的示例
4. 带真实 key 时至少有一条高德请求可通

## 1. 只读能力面，无需 API Key

```bash
uv run --project . amap-mcp-server docs targets
uv run --project . amap-mcp-server docs show route.driving.plan
uv run --project . amap-mcp-server docs export --format markdown
uv run --project . amap-mcp-server docs runtime
```

预期：

- 能看到 `geo`、`poi`、`route`、`weather` 四个 command
- `route.driving.plan` 的参数、示例、cite、acceptance hint 可读
- export 产物与 `docs/reference/commands.md` 同源
- `docs runtime` 能看到当前 `runtime_backend` 与 `runtime_phase`

## 2. 本地 smoke，无需手写参数

```bash
uv run --project . amap-mcp-server smoke list
```

如果当前 shell 已经设置有效 key，可直接执行：

```bash
uv run --project . amap-mcp-server smoke run route.distance.measure
```

预期：

- `smoke list` 能返回每个 target 的默认 example
- `smoke run` 在成功时返回 `ok: true`
- 如果失败，可把错误继续交给 `smoke explain`

## 3. 错误解释

```bash
uv run --project . amap-mcp-server smoke explain \
  route.transit.plan \
  "missing required argument: origin_city"
```

预期：

- 能返回结构化的 `suggestions`
- cite 里包含 `help_target`、`raw_tools`、`impl_refs`

## 4. MCP Serve

```bash
export AMAP_MAPS_API_KEY=your_amap_maps_api_key
uv run --project . amap-mcp-server serve stdio
```

SSE：

```bash
uv run --project . amap-mcp-server serve sse --host 0.0.0.0 --port 8000
```

Streamable HTTP：

```bash
uv run --project . amap-mcp-server serve streamable-http --host 0.0.0.0 --port 8000
```

## 5. 与 trip-planner-workspace 的最小闭环

在 `anyagent-apps/examples/trip-planner-workspace` 里把 MCP 指向本地仓库后，至少验证一条链路：

1. `poi.keyword.search`
2. `route.driving.plan`
3. `weather.city.get`

如果 trip-planner 上游消费姿势发生变化，应优先回到这里同步 acceptance 说明。
