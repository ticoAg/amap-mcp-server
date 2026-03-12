# Raw Tools Reference

这份文档记录底层 `maps_*` 工具，用于兼容已有客户端、调试 HTTP 响应和核对 facade 映射。默认主路径仍然是 facade：`ls / help / run / explain`。

## Mapping

| Raw Tool | Recommended Facade Target |
|---|---|
| `maps_geo` | `geo.address.resolve` |
| `maps_regeocode` | `geo.location.reverse` |
| `maps_ip_location` | `geo.ip.locate` |
| `maps_weather` | `weather.city.get` |
| `maps_text_search` | `poi.keyword.search` |
| `maps_around_search` | `poi.around.search` |
| `maps_search_detail` | `poi.place.detail` |
| `maps_distance` | `route.distance.measure` |
| `maps_bicycling_by_address` | `route.bicycling.plan` |
| `maps_bicycling_by_coordinates` | `route.bicycling.plan` |
| `maps_direction_walking_by_address` | `route.walking.plan` |
| `maps_direction_walking_by_coordinates` | `route.walking.plan` |
| `maps_direction_driving_by_address` | `route.driving.plan` |
| `maps_direction_driving_by_coordinates` | `route.driving.plan` |
| `maps_direction_transit_integrated_by_address` | `route.transit.plan` |
| `maps_direction_transit_integrated_by_coordinates` | `route.transit.plan` |

## Notes

- 路线类 raw tools 同时存在地址版和坐标版；facade 已经统一成一个 `route.*.plan` target。
- raw tools 更贴近高德接口，不一定具备 facade 的错误建议、acceptance hint 和上层语义。
- 如果要新增能力，建议先补 facade target，再决定是否暴露新的 raw tool。
