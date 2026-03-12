# Error Reference

`explain` 会把常见失败模式归一化成下一步建议。下面是当前仓库优先覆盖的错误类型。

## Key / Auth

常见错误：

- `AMAP_MAPS_API_KEY environment variable is required`
- `INVALID_USER_KEY`
- `USER_KEY`

建议动作：

- 检查当前 shell 是否设置了有效的 `AMAP_MAPS_API_KEY`
- 如果是远端部署，确认 server 进程而不是客户端进程持有该环境变量

## Quota / Rate Limit

常见错误：

- `DAILY_QUERY_OVER_LIMIT`
- `too many requests`
- `quota`

建议动作：

- 检查当前 key 配额
- 适当降低请求频率
- 必要时切换 key

## Geocoding Miss

常见错误：

- `No geocoding results found`

建议动作：

- 补充更精确的地址
- 增加 `city`
- 先用 `poi.keyword.search` 找候选，再做地址解析

## Transit City Params

常见错误：

- 缺少 `origin_city`
- 缺少 `destination_city`

建议动作：

- 公共交通规划显式补上起终点城市
- 跨城场景下不要只传坐标

## CLI Example

```bash
uv run --project . amap-mcp-server smoke explain \
  route.transit.plan \
  "missing required argument: origin_city"
```
