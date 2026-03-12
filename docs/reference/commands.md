<!-- Generated from `amap_mcp_server.server.COMMAND_ACTIONS`. -->
# Command Reference

默认推荐 agent 先通过 `ls -> help -> run -> explain` 使用高德能力。
raw `maps_*` 工具仍然保留用于兼容与调试，但不是默认主路径。

## `geo`

### `geo.address`

#### `geo.address.resolve`

将结构化地址解析为经纬度，适合地点确认、酒店/景点纠偏和路线规划前校验。

适用场景：
- 在行程开始前把模糊地点名解析成可用于 POI 和路线规划的坐标。
- 对酒店、景点、车站等候选地点做纠偏与同名消歧。

参数：
- `address`: 结构化地址或地标名称，例如“杭州市西湖区灵隐路法云弄1号”。
- `city`: 可选城市，用于提高地理编码准确性。

示例：
```json
{
  "address": "杭州市西湖区灵隐路法云弄1号",
  "city": "杭州"
}
```

Cites：
- raw tools: `maps_geo`
- docs: https://lbs.amap.com/api/webservice/guide/api/georegeo
- impl: `amap_mcp_server/server.py::maps_geo`
- acceptance: 先执行地址解析，再把返回的坐标接给 `route.*.plan` 或 `poi.around.search`。

### `geo.ip`

#### `geo.ip.locate`

根据 IP 反查大致地理位置，适合城市级定位，不适合精确路线规划。

适用场景：
- 在没有显式城市信息时做粗粒度城市猜测。
- 根据用户来源 IP 预填默认城市，再交给后续 POI 或天气查询细化。

参数：
- `ip`: 待查询的 IPv4 地址。

示例：
```json
{
  "ip": "1.2.3.4"
}
```

Cites：
- raw tools: `maps_ip_location`
- docs: https://lbs.amap.com/api/webservice/guide/api/ipconfig
- impl: `amap_mcp_server/server.py::maps_ip_location`
- acceptance: 城市级定位只适合作为默认值，不应直接用于精确路线规划。

### `geo.location`

#### `geo.location.reverse`

将经纬度反查为行政区划与地址上下文，适合校验坐标归属地。

适用场景：
- 校验来自外部系统的坐标是否真的落在目标城市或景区。
- 给路线或 POI 结果补充行政区划上下文。

参数：
- `location`: 经纬度坐标，格式为“经度,纬度”。

示例：
```json
{
  "location": "120.130663,30.240018"
}
```

Cites：
- raw tools: `maps_regeocode`
- docs: https://lbs.amap.com/api/webservice/guide/api/georegeo
- impl: `amap_mcp_server/server.py::maps_regeocode`
- acceptance: 可用 `poi.keyword.search` 找到地点后，再用其坐标做一次反查验证。

## `poi`

### `poi.around`

#### `poi.around.search`

围绕一个中心点搜周边 POI，适合酒店周边、美食周边、车站周边筛选。

适用场景：
- 围绕酒店、景点或车站找周边餐饮与配套设施。
- 围绕行程中的锚点做局部探索，而不是全城搜索。

参数：
- `location`: 中心点经纬度，格式为“经度,纬度”。
- `radius`: 搜索半径（米），默认 1000。
- `keywords`: 可选关键词，例如“咖啡”“酒店”“地铁站”。

示例：
```json
{
  "location": "120.130663,30.240018",
  "radius": "1500",
  "keywords": "酒店"
}
```

Cites：
- raw tools: `maps_around_search`
- docs: https://lbs.amap.com/api/webservice/guide/api/search
- impl: `amap_mcp_server/server.py::maps_around_search`
- acceptance: 通常先用 `geo.address.resolve` 或 `poi.keyword.search` 拿到中心点，再做 around 搜索。

### `poi.keyword`

#### `poi.keyword.search`

按关键词做 POI 搜索，适合搜景点、商圈、酒店、美食等候选列表。

适用场景：
- 按城市和主题筛出候选景点、商圈、酒店或餐厅。
- 在 trip-planner 中为某一站点生成备选地点列表。

参数：
- `keywords`: 搜索关键词，例如“西湖 景点”或“北京南站 酒店”。
- `city`: 可选城市名称，建议在行程场景中尽量提供。
- `citylimit`: 是否限制在指定城市内搜索，字符串 true/false，默认 false。

示例：
```json
{
  "keywords": "西湖 景点",
  "city": "杭州",
  "citylimit": "true"
}
```

Cites：
- raw tools: `maps_text_search`
- docs: https://lbs.amap.com/api/webservice/guide/api/search
- impl: `amap_mcp_server/server.py::maps_text_search`
- acceptance: 如果结果过宽，先补 `city` 或改用 `poi.around.search` 收窄范围。

### `poi.place`

#### `poi.place.detail`

按 POI ID 查看详细信息，适合在候选确认后补地址、营业区和细节。

适用场景：
- 对候选 POI 进一步补充地址、商圈和业务扩展信息。
- 在 agent 已选定某个候选地点后做最终确认。

参数：
- `id`: POI ID，一般来自 keyword/around 搜索结果。

示例：
```json
{
  "id": "B0FFG7JQ2E"
}
```

Cites：
- raw tools: `maps_search_detail`
- docs: https://lbs.amap.com/api/webservice/guide/api/search
- impl: `amap_mcp_server/server.py::maps_search_detail`
- acceptance: 该 action 通常紧跟在 `poi.keyword.search` 或 `poi.around.search` 之后。

## `route`

### `route.bicycling`

#### `route.bicycling.plan`

规划骑行路线。优先使用地址版参数，只有明确需要时再传坐标。

适用场景：
- 规划景点之间的低碳短距离通勤。
- 在城市游场景里对比步行与骑行路线成本。

参数：
- `origin_address`: 起点地址；与 destination_address 一起传时优先走地址版。
- `destination_address`: 终点地址；与 origin_address 一起传时优先走地址版。
- `origin_city`: 起点城市；建议显式提供以提高地址解析准确性。
- `destination_city`: 终点城市；建议显式提供以提高地址解析准确性。
- `origin`: 起点坐标，格式“经度,纬度”；仅在不用地址版时传。
- `destination`: 终点坐标，格式“经度,纬度”；仅在不用地址版时传。

示例：
```json
{
  "origin_address": "西湖文化广场",
  "destination_address": "武林广场",
  "origin_city": "杭州",
  "destination_city": "杭州"
}
```

Cites：
- raw tools: `maps_bicycling_by_address`, `maps_bicycling_by_coordinates`
- docs: https://lbs.amap.com/api/webservice/guide/api/direction
- impl: `amap_mcp_server/server.py::_run_route_bicycling`
- impl: `amap_mcp_server/server.py::maps_bicycling_by_address`
- impl: `amap_mcp_server/server.py::maps_bicycling_by_coordinates`
- acceptance: 默认先传地址版参数；只有坐标已明确且不需要再次解析时再传 `origin` / `destination`。

### `route.distance`

#### `route.distance.measure`

测量起终点距离，可选驾车、步行或球面距离模式。

适用场景：
- 快速比较多个候选地点到同一终点的距离。
- 在正式路线规划前做粗粒度筛选。

参数：
- `origins`: 起点坐标，可为一个或多个，多个时用竖线分隔。
- `destination`: 终点坐标，格式“经度,纬度”。
- `type`: 距离类型，默认 1；具体模式见高德距离测量文档。

示例：
```json
{
  "origins": "120.130663,30.240018",
  "destination": "120.155070,30.274085",
  "type": "1"
}
```

Cites：
- raw tools: `maps_distance`
- docs: https://lbs.amap.com/api/webservice/guide/api/distance
- impl: `amap_mcp_server/server.py::maps_distance`
- acceptance: 多个起点可用 `|` 拼接，适合先粗筛再进入详细路线规划。

### `route.driving`

#### `route.driving.plan`

规划驾车路线。优先使用地址版参数，只有明确需要时再传坐标。

适用场景：
- 规划机场、车站与酒店之间的驾车或打车路线。
- 评估多个景点之间的车程成本。

参数：
- `origin_address`: 起点地址；与 destination_address 一起传时优先走地址版。
- `destination_address`: 终点地址；与 origin_address 一起传时优先走地址版。
- `origin_city`: 起点城市；建议显式提供以提高地址解析准确性。
- `destination_city`: 终点城市；建议显式提供以提高地址解析准确性。
- `origin`: 起点坐标，格式“经度,纬度”；仅在不用地址版时传。
- `destination`: 终点坐标，格式“经度,纬度”；仅在不用地址版时传。

示例：
```json
{
  "origin_address": "杭州东站",
  "destination_address": "西湖风景名胜区",
  "origin_city": "杭州",
  "destination_city": "杭州"
}
```

Cites：
- raw tools: `maps_direction_driving_by_address`, `maps_direction_driving_by_coordinates`
- docs: https://lbs.amap.com/api/webservice/guide/api/direction
- impl: `amap_mcp_server/server.py::_run_route_driving`
- impl: `amap_mcp_server/server.py::maps_direction_driving_by_address`
- impl: `amap_mcp_server/server.py::maps_direction_driving_by_coordinates`
- acceptance: 如果要给用户呈现行程时长和距离，优先选驾车路线再对比公共交通。

### `route.transit`

#### `route.transit.plan`

规划公共交通路线。优先使用地址版参数；跨城时必须提供起终点城市。

适用场景：
- 规划城市内公共交通换乘方案。
- 在跨城场景里比较高铁、公交、地铁等综合通勤成本。

参数：
- `origin_address`: 起点地址；与 destination_address 一起传时优先走地址版。
- `destination_address`: 终点地址；与 origin_address 一起传时优先走地址版。
- `origin_city`: 起点城市；地址版和跨城场景都建议显式提供。
- `destination_city`: 终点城市；地址版和跨城场景都建议显式提供。
- `origin`: 起点坐标，格式“经度,纬度”；仅在不用地址版时传。
- `destination`: 终点坐标，格式“经度,纬度”；仅在不用地址版时传。

示例：
```json
{
  "origin_address": "杭州东站",
  "destination_address": "西湖风景名胜区",
  "origin_city": "杭州",
  "destination_city": "杭州"
}
```

Cites：
- raw tools: `maps_direction_transit_integrated_by_address`, `maps_direction_transit_integrated_by_coordinates`
- docs: https://lbs.amap.com/api/webservice/guide/api/direction
- impl: `amap_mcp_server/server.py::_run_route_transit`
- impl: `amap_mcp_server/server.py::maps_direction_transit_integrated_by_address`
- impl: `amap_mcp_server/server.py::maps_direction_transit_integrated_by_coordinates`
- acceptance: 公共交通规划对城市参数更敏感；跨城场景务必同时传 `origin_city` 和 `destination_city`。

### `route.walking`

#### `route.walking.plan`

规划步行路线。优先使用地址版参数，只有明确需要时再传坐标。

适用场景：
- 规划园区、景区、商圈内的短距离步行路线。
- 为行程卡片补充步行时间和分段导航。

参数：
- `origin_address`: 起点地址；与 destination_address 一起传时优先走地址版。
- `destination_address`: 终点地址；与 origin_address 一起传时优先走地址版。
- `origin_city`: 起点城市；建议显式提供以提高地址解析准确性。
- `destination_city`: 终点城市；建议显式提供以提高地址解析准确性。
- `origin`: 起点坐标，格式“经度,纬度”；仅在不用地址版时传。
- `destination`: 终点坐标，格式“经度,纬度”；仅在不用地址版时传。

示例：
```json
{
  "origin_address": "灵隐寺",
  "destination_address": "飞来峰",
  "origin_city": "杭州",
  "destination_city": "杭州"
}
```

Cites：
- raw tools: `maps_direction_walking_by_address`, `maps_direction_walking_by_coordinates`
- docs: https://lbs.amap.com/api/webservice/guide/api/direction
- impl: `amap_mcp_server/server.py::_run_route_walking`
- impl: `amap_mcp_server/server.py::maps_direction_walking_by_address`
- impl: `amap_mcp_server/server.py::maps_direction_walking_by_coordinates`
- acceptance: 景区内步行路线建议先用地址版，方便 agent 在输出中带回原始地址。

## `weather`

### `weather.city`

#### `weather.city.get`

查询城市天气，适合给行程附加天气风险提示。

适用场景：
- 给每日行程补充天气风险提示。
- 比较多个候选城市的天气条件，辅助出行建议。

参数：
- `city`: 城市名称或 adcode。

示例：
```json
{
  "city": "杭州"
}
```

Cites：
- raw tools: `maps_weather`
- docs: https://lbs.amap.com/api/webservice/guide/api/weatherinfo
- impl: `amap_mcp_server/server.py::maps_weather`
- acceptance: 通常在行程骨架稳定后再查询天气，避免过早请求。
