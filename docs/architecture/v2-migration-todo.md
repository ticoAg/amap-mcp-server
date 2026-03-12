# MCP Python SDK v2 Migration TODO

## Goal

把 `amap-mcp-server` 迁移到官方 MCP Python SDK v2 的 server 设计，同时保持 Amap facade 的主路径不变：

- `ls`
- `help`
- `run`
- `explain`

官方参考：

- MCP 官方仓库：`https://github.com/modelcontextprotocol/python-sdk`
- MCP Python SDK v2：`https://github.com/modelcontextprotocol/python-sdk/blob/main/README.v2.md`

## Principles

- 不为旧 runtime 保留兼容层
- 先稳住 facade 语义，再切 runtime
- transport 继续一等支持：`stdio`、`sse`、`streamable-http`
- 一切迁移都以最小可验证闭环推进

## Status

### Phase 0: 设计冻结

- [x] 明确 `anyagent = federation`、`amap-mcp-server = facade`
- [x] README 与 architecture 文档改到 v2 方向
- [x] 不再新增旧 FastMCP 风格兼容说明

### Phase 1: 代码结构收敛

- [x] 把业务逻辑与 MCP runtime 注册拆分
- [x] 引入独立 runtime adapter：`amap_mcp_server/mcp_runtime.py`
- [x] CLI 改为只依赖 runtime adapter，而不是直接依赖业务模块中的 MCP 对象
- [x] 抽出稳定的 `RuntimeAdapter` 接口与 transport settings 模型
- [x] 升级到当前可获取的最新稳定 `mcp` 版本

### Phase 2: 设计锚点

- [x] 用 adapter 接口表达“未来切官方 v2 时只替换 runtime 实现”
- [x] 提供可读的 runtime 结构快照，帮助验收当前仍处于 `v2-ready` 阶段
- [ ] 补一条 acceptance，断言 runtime snapshot 中会标记当前 adapter 与 migration phase

### Phase 3: 官方 v2 runtime 切换

- [ ] 切换 `mcp_runtime.py` 到官方 v2 `MCPServer`
- [ ] 去掉 runtime adapter 中对旧 FastMCP API 的直接依赖
- [ ] 验证 raw tools 与 facade tools 的注册方式在 v2 下等价
- [ ] 复核三种 transport 的 endpoint 与 CLI 参数

### Phase 4: 上游接线同步

- [ ] 更新 `trip-planner-workspace` 的 `mcp.json`
- [ ] 更新 workspace skill 提示，明确只使用 facade 主路径
- [ ] 增补一条 `anyagent` 消费侧最小闭环验证

## Current Blockers

- 官方 `README.v2.md` 对应 runtime 在当前可访问分发源里尚未直接可用
- 直接从 GitHub `main` 拉取依赖时，当前环境访问 `github.com:443` 失败

## Exit Criteria

只有以下条件同时满足，才算“完成 v2 迁移”：

1. `mcp_runtime.py` 已切换到官方 v2 runtime
2. `serve stdio|sse|streamable-http` 都能真实启动
3. facade 命令面输出与当前 reference 文档一致
4. acceptance 至少覆盖一条真实 transport 闭环
