import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence
import requests

def get_api_key() -> str:
    """Get the Amap Maps API key from environment variables."""
    api_key = os.getenv("AMAP_MAPS_API_KEY")
    if not api_key:
        message = "\n".join([
            "❌ Missing required credential: AMAP_MAPS_API_KEY",
            "",
            "To get your Amap Maps API Key:",
            "  1. Visit https://console.amap.com/ → Create application",
            "  2. Add a 'Web Service' key type",
            "  3. Copy the generated API Key",
            "",
            "Provide via environment variable:",
            "  export AMAP_MAPS_API_KEY=your_key_here",
            "",
            "📖 Amap docs: https://lbs.amap.com/api/webservice/guide/create-project/get-key",
        ])
        raise ValueError(message)
    return api_key

@dataclass(frozen=True)
class CommandAction:
    command: str
    resource: str
    action: str
    summary: str
    raw_tools: tuple[str, ...]
    docs_url: str
    arg_docs: Dict[str, str]
    use_cases: tuple[str, ...]
    examples: tuple[Dict[str, Any], ...]
    acceptance_hint: str
    impl_refs: tuple[str, ...]
    runner: Callable[[Dict[str, Any]], Dict[str, Any]]

    @property
    def target(self) -> str:
        return f"{self.command}.{self.resource}.{self.action}"


def _request_json(path: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(
        f"https://restapi.amap.com{path}",
        params={"key": get_api_key(), **params},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("invalid JSON response from Amap")
    return data


def _status_error(data: Dict[str, Any], *, label: str) -> Optional[str]:
    if data.get("status") == "1":
        return None
    return f"{label} failed: {data.get('info') or data.get('infocode')}"


def _safe_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _first_geocoded_location(address: str, city: Optional[str]) -> str:
    result = maps_geo(address, city)
    if "error" in result:
        raise ValueError(str(result["error"]))
    geocodes = result.get("return")
    if not isinstance(geocodes, list) or not geocodes:
        raise ValueError("No geocoding results found")
    location = geocodes[0].get("location")
    if not isinstance(location, str) or not location.strip():
        raise ValueError("Could not extract coordinates from geocoding result")
    return location.strip()


def _resolve_route_points(
    *,
    origin_address: Optional[str],
    destination_address: Optional[str],
    origin_city: Optional[str],
    destination_city: Optional[str],
    origin: Optional[str],
    destination: Optional[str],
) -> Dict[str, Any]:
    if origin_address and destination_address:
        origin_location = _first_geocoded_location(origin_address, origin_city)
        destination_location = _first_geocoded_location(destination_address, destination_city)
        return {
            "origin": origin_location,
            "destination": destination_location,
            "addresses": {
                "origin": {"address": origin_address, "coordinates": origin_location},
                "destination": {"address": destination_address, "coordinates": destination_location},
            },
        }
    if not origin or not destination:
        raise ValueError("Provide either origin/destination addresses or origin/destination coordinates")
    return {"origin": origin, "destination": destination}


def _with_addresses(route_result: Dict[str, Any], resolved: Dict[str, Any]) -> Dict[str, Any]:
    if "error" not in route_result and "addresses" in resolved:
        route_result["addresses"] = resolved["addresses"]
    return route_result

def maps_regeocode(location: str) -> Dict[str, Any]:
    """将一个高德经纬度坐标转换为行政区划地址信息"""
    try:
        data = _request_json("/v3/geocode/regeo", params={"location": location})
        error = _status_error(data, label="RGeocoding")
        if error is not None:
            return {"error": error}
        return {
            "province": data["regeocode"]["addressComponent"]["province"],
            "city": data["regeocode"]["addressComponent"]["city"],
            "district": data["regeocode"]["addressComponent"]["district"]
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_geo(address: str, city: Optional[str] = None) -> Dict[str, Any]:
    """将详细的结构化地址转换为经纬度坐标。支持对地标性名胜景区、建筑物名称解析为经纬度坐标"""
    try:
        params = {"address": address}
        if city:
            params["city"] = city
        data = _request_json("/v3/geocode/geo", params=params)
        error = _status_error(data, label="Geocoding")
        if error is not None:
            return {"error": error}
        geocodes = data.get("geocodes", [])
        results = []
        for geo in geocodes:
            results.append({
                "country": geo.get("country"),
                "province": geo.get("province"),
                "city": geo.get("city"),
                "citycode": geo.get("citycode"),
                "district": geo.get("district"),
                "street": geo.get("street"),
                "number": geo.get("number"),
                "adcode": geo.get("adcode"),
                "location": geo.get("location"),
                "level": geo.get("level")
            })
        return {"return": results}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_ip_location(ip: str) -> Dict[str, Any]:
    """IP 定位根据用户输入的 IP 地址，定位 IP 的所在位置"""
    try:
        data = _request_json("/v3/ip", params={"ip": ip})
        error = _status_error(data, label="IP Location")
        if error is not None:
            return {"error": error}
        return {
            "province": data.get("province"),
            "city": data.get("city"),
            "adcode": data.get("adcode"),
            "rectangle": data.get("rectangle")
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_weather(city: str) -> Dict[str, Any]:
    """根据城市名称或者标准adcode查询指定城市的天气"""
    try:
        data = _request_json("/v3/weather/weatherInfo", params={"city": city, "extensions": "all"})
        error = _status_error(data, label="Get weather")
        if error is not None:
            return {"error": error}
        forecasts = data.get("forecasts", [])
        if not forecasts:
            return {"error": "No forecast data available"}
            
        return {
            "city": forecasts[0]["city"],
            "forecasts": forecasts[0]["casts"]
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_bicycling_by_address(origin_address: str, destination_address: str, origin_city: Optional[str] = None, destination_city: Optional[str] = None) -> Dict[str, Any]:
    """Plans a bicycle route between two locations using addresses. Unless you have a specific reason to use coordinates, it's recommended to use this tool.
    
    Args:
        origin_address (str): Starting point address (e.g. "北京市朝阳区阜通东大街6号")
        destination_address (str): Ending point address (e.g. "北京市海淀区上地十街10号")
        origin_city (Optional[str]): Optional city name for the origin address to improve geocoding accuracy
        destination_city (Optional[str]): Optional city name for the destination address to improve geocoding accuracy
        
    Returns:
        Dict[str, Any]: Route information including distance, duration, and turn-by-turn instructions.
        Considers bridges, one-way streets, and road closures. Supports routes up to 500km.
    """
    try:
        resolved = _resolve_route_points(
            origin_address=origin_address,
            destination_address=destination_address,
            origin_city=origin_city,
            destination_city=destination_city,
            origin=None,
            destination=None,
        )
        return _with_addresses(
            maps_bicycling_by_coordinates(resolved["origin"], resolved["destination"]),
            resolved,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"Route planning failed: {str(e)}"}
    
def maps_bicycling_by_coordinates(origin_coordinates: str, destination_coordinates: str) -> Dict[str, Any]:
    """Plans a bicycle route between two coordinates.
    
    Args:
        origin_coordinates (str): Starting point coordinates in the format "longitude,latitude" (e.g. "116.434307,39.90909")
        destination_coordinates (str): Ending point coordinates in the format "longitude,latitude" (e.g. "116.434307,39.90909")
        
    Returns:
        Dict[str, Any]: Route information including distance, duration, and turn-by-turn instructions.
        Considers bridges, one-way streets, and road closures. Supports routes up to 500km.
    """
    try:
        response = requests.get(
            "https://restapi.amap.com/v4/direction/bicycling",
            params={
                "key": get_api_key(),
                "origin": origin_coordinates,
                "destination": destination_coordinates
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("errcode") != 0:
            return {"error": f"Direction bicycling failed: {data.get('info') or data.get('infocode')}"}
            
        paths = []
        for path in data["data"]["paths"]:
            steps = []
            for step in path["steps"]:
                steps.append({
                    "instruction": step.get("instruction"),
                    "road": step.get("road"),
                    "distance": step.get("distance"),
                    "orientation": step.get("orientation"),
                    "duration": step.get("duration")
                })
            paths.append({
                "distance": path.get("distance"),
                "duration": path.get("duration"),
                "steps": steps
            })
            
        return {
            "data": {
                "origin": data["data"]["origin"],
                "destination": data["data"]["destination"],
                "paths": paths
            }
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_direction_walking_by_address(origin_address: str, destination_address: str, origin_city: Optional[str] = None, destination_city: Optional[str] = None) -> Dict[str, Any]:
    """Plans a walking route between two locations using addresses. Unless you have a specific reason to use coordinates, it's recommended to use this tool.
    
    Args:
        origin_address (str): Starting point address (e.g. "北京市朝阳区阜通东大街6号")
        destination_address (str): Ending point address (e.g. "北京市海淀区上地十街10号")
        origin_city (Optional[str]): Optional city name for the origin address to improve geocoding accuracy
        destination_city (Optional[str]): Optional city name for the destination address to improve geocoding accuracy
        
    Returns:
        Dict[str, Any]: Route information including distance, duration, and turn-by-turn instructions.
        Supports routes up to 100km.
    """
    try:
        resolved = _resolve_route_points(
            origin_address=origin_address,
            destination_address=destination_address,
            origin_city=origin_city,
            destination_city=destination_city,
            origin=None,
            destination=None,
        )
        return _with_addresses(
            maps_direction_walking_by_coordinates(resolved["origin"], resolved["destination"]),
            resolved,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"Route planning failed: {str(e)}"}

def maps_direction_walking_by_coordinates(origin: str, destination: str) -> Dict[str, Any]:
    """步行路径规划 API 可以根据输入起点终点经纬度坐标规划100km 以内的步行通勤方案，并且返回通勤方案的数据
    
    Args:
        origin (str): 起点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        destination (str): 终点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        
    Returns:
        Dict[str, Any]: 包含距离、时长和详细导航信息的路线数据
    """
    try:
        response = requests.get(
            "https://restapi.amap.com/v3/direction/walking",
            params={
                "key": get_api_key(),
                "origin": origin,
                "destination": destination
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if data["status"] != "1":
            return {"error": f"Direction Walking failed: {data.get('info') or data.get('infocode')}"}
            
        paths = []
        for path in data["route"]["paths"]:
            steps = []
            for step in path["steps"]:
                steps.append({
                    "instruction": step.get("instruction"),
                    "road": step.get("road"),
                    "distance": step.get("distance"),
                    "orientation": step.get("orientation"),
                    "duration": step.get("duration")
                })
            paths.append({
                "distance": path.get("distance"),
                "duration": path.get("duration"),
                "steps": steps
            })
            
        return {
            "route": {
                "origin": data["route"]["origin"],
                "destination": data["route"]["destination"],
                "paths": paths
            }
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_direction_driving_by_address(origin_address: str, destination_address: str, origin_city: Optional[str] = None, destination_city: Optional[str] = None) -> Dict[str, Any]:
    """Plans a driving route between two locations using addresses. Unless you have a specific reason to use coordinates, it's recommended to use this tool.
    
    Args:
        origin_address (str): Starting point address (e.g. "北京市朝阳区阜通东大街6号")
        destination_address (str): Ending point address (e.g. "北京市海淀区上地十街10号")
        origin_city (Optional[str]): Optional city name for the origin address to improve geocoding accuracy
        destination_city (Optional[str]): Optional city name for the destination address to improve geocoding accuracy
        
    Returns:
        Dict[str, Any]: Route information including distance, duration, and turn-by-turn instructions.
        Considers traffic conditions and road restrictions.
    """
    try:
        resolved = _resolve_route_points(
            origin_address=origin_address,
            destination_address=destination_address,
            origin_city=origin_city,
            destination_city=destination_city,
            origin=None,
            destination=None,
        )
        return _with_addresses(
            maps_direction_driving_by_coordinates(resolved["origin"], resolved["destination"]),
            resolved,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"Route planning failed: {str(e)}"}

def maps_direction_driving_by_coordinates(origin: str, destination: str) -> Dict[str, Any]:
    """驾车路径规划 API 可以根据用户起终点经纬度坐标规划以小客车、轿车通勤出行的方案，并且返回通勤方案的数据
    
    Args:
        origin (str): 起点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        destination (str): 终点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        
    Returns:
        Dict[str, Any]: 包含距离、时长和详细导航信息的路线数据
    """
    try:
        response = requests.get(
            "https://restapi.amap.com/v3/direction/driving",
            params={
                "key": get_api_key(),
                "origin": origin,
                "destination": destination
            }
        )
        response.raise_for_status()
        data = response.json()
        
        if data["status"] != "1":
            return {"error": f"Direction Driving failed: {data.get('info') or data.get('infocode')}"}
            
        paths = []
        for path in data["route"]["paths"]:
            steps = []
            for step in path["steps"]:
                steps.append({
                    "instruction": step.get("instruction"),
                    "road": step.get("road"),
                    "distance": step.get("distance"),
                    "orientation": step.get("orientation"),
                    "duration": step.get("duration")
                })
            paths.append({
                "path": path.get("path"),
                "distance": path.get("distance"),
                "duration": path.get("duration"),
                "steps": steps
            })
            
        return {
            "route": {
                "origin": data["route"]["origin"],
                "destination": data["route"]["destination"],
                "paths": paths
            }
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_direction_transit_integrated_by_address(origin_address: str, destination_address: str, origin_city: str, destination_city: str) -> Dict[str, Any]:
    """Plans a public transit route between two locations using addresses. Unless you have a specific reason to use coordinates, it's recommended to use this tool.
    
    Args:
        origin_address (str): Starting point address (e.g. "北京市朝阳区阜通东大街6号")
        destination_address (str): Ending point address (e.g. "北京市海淀区上地十街10号")
        origin_city (str): City name for the origin address (required for cross-city transit)
        destination_city (str): City name for the destination address (required for cross-city transit)
        
    Returns:
        Dict[str, Any]: Route information including distance, duration, and detailed transit instructions.
        Considers various public transit options including buses, subways, and trains.
    """
    try:
        resolved = _resolve_route_points(
            origin_address=origin_address,
            destination_address=destination_address,
            origin_city=origin_city,
            destination_city=destination_city,
            origin=None,
            destination=None,
        )
        return _with_addresses(
            maps_direction_transit_integrated_by_coordinates(
                resolved["origin"],
                resolved["destination"],
                origin_city,
                destination_city,
            ),
            resolved,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"Route planning failed: {str(e)}"}

def maps_direction_transit_integrated_by_coordinates(origin: str, destination: str, city: str, cityd: str) -> Dict[str, Any]:
    """根据用户起终点经纬度坐标规划综合各类公共（火车、公交、地铁）交通方式的通勤方案，并且返回通勤方案的数据，跨城场景下必须传起点城市与终点城市

    Args:
        origin (str): 起点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        destination (str): 终点经纬度坐标，格式为"经度,纬度" (例如："116.434307,39.90909")
        city (str): 起点城市名称
        cityd (str): 终点城市名称

    Returns:
        Dict[str, Any]: 包含距离、时长和详细公共交通信息的路线数据
    """
    try:
        data = _request_json(
            "/v3/direction/transit/integrated",
            params={
                "origin": origin,
                "destination": destination,
                "city": city,
                "cityd": cityd,
            },
        )
        error = _status_error(data, label="Direction Transit Integrated")
        if error is not None:
            return {"error": error}

        # Safe handling for route data - it might be a list or missing
        route_data = data.get("route")
        if not isinstance(route_data, dict):
            return {"error": "No route data available"}

        transits = []
        transits_data = route_data.get("transits")
        if isinstance(transits_data, list):
            for transit in transits_data:
                # Ensure transit is a dict
                if not isinstance(transit, dict):
                    continue

                segments = []
                segments_data = transit.get("segments")
                if isinstance(segments_data, list):
                    for segment in segments_data:
                        # Ensure segment is a dict
                        if not isinstance(segment, dict):
                            continue

                        # Safe handling for walking data
                        walking_data = segment.get("walking")
                        if not isinstance(walking_data, dict):
                            walking_data = {}

                        walking_steps = []
                        steps_data = walking_data.get("steps")
                        if isinstance(steps_data, list):
                            for step in steps_data:
                                if isinstance(step, dict):
                                    walking_steps.append({
                                        "instruction": step.get("instruction"),
                                        "road": step.get("road"),
                                        "distance": step.get("distance"),
                                        "action": step.get("action"),
                                        "assistant_action": step.get("assistant_action")
                                    })

                        # Safe handling for bus data
                        bus_data = segment.get("bus")
                        if not isinstance(bus_data, dict):
                            bus_data = {}

                        buslines = []
                        buslines_data = bus_data.get("buslines")
                        if isinstance(buslines_data, list):
                            for busline in buslines_data:
                                # Ensure busline is a dict
                                if not isinstance(busline, dict):
                                    continue

                                via_stops = []
                                via_stops_data = busline.get("via_stops")
                                if isinstance(via_stops_data, list):
                                    for stop in via_stops_data:
                                        if isinstance(stop, dict):
                                            via_stops.append({"name": stop.get("name")})

                                dep_stop = busline.get("departure_stop")
                                if not isinstance(dep_stop, dict):
                                    dep_stop = {}

                                arr_stop = busline.get("arrival_stop")
                                if not isinstance(arr_stop, dict):
                                    arr_stop = {}

                                buslines.append({
                                    "name": busline.get("name"),
                                    "departure_stop": {"name": dep_stop.get("name")},
                                    "arrival_stop": {"name": arr_stop.get("name")},
                                    "distance": busline.get("distance"),
                                    "duration": busline.get("duration"),
                                    "via_stops": via_stops
                                })

                        # Safe handling for other optional fields
                        entrance_data = segment.get("entrance")
                        if not isinstance(entrance_data, dict):
                            entrance_data = {}

                        exit_data = segment.get("exit")
                        if not isinstance(exit_data, dict):
                            exit_data = {}

                        railway_data = segment.get("railway")
                        if not isinstance(railway_data, dict):
                            railway_data = {}

                        segments.append({
                            "walking": {
                                "origin": walking_data.get("origin"),
                                "destination": walking_data.get("destination"),
                                "distance": walking_data.get("distance"),
                                "duration": walking_data.get("duration"),
                                "steps": walking_steps
                            },
                            "bus": {"buslines": buslines},
                            "entrance": {"name": entrance_data.get("name")},
                            "exit": {"name": exit_data.get("name")},
                            "railway": {
                                "name": railway_data.get("name"),
                                "trip": railway_data.get("trip")
                            }
                        })

                transits.append({
                    "duration": transit.get("duration"),
                    "walking_distance": transit.get("walking_distance"),
                    "segments": segments
                })

        return {
            "route": {
                "origin": route_data.get("origin"),
                "destination": route_data.get("destination"),
                "distance": route_data.get("distance"),
                "transits": transits
            }
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_distance(origins: str, destination: str, type: str = "1") -> Dict[str, Any]:
    """测量两个经纬度坐标之间的距离,支持驾车、步行以及球面距离测量"""
    try:
        data = _request_json(
            "/v3/distance",
            params={"origins": origins, "destination": destination, "type": type},
        )
        error = _status_error(data, label="Direction Distance")
        if error is not None:
            return {"error": error}
            
        results = []
        for result in data["results"]:
            results.append({
                "origin_id": result.get("origin_id"),
                "dest_id": result.get("dest_id"),
                "distance": result.get("distance"),
                "duration": result.get("duration")
            })
            
        return {"results": results}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_text_search(keywords: str, city: str = "", citylimit: str = "false") -> Dict[str, Any]:
    """关键词搜索 API 根据用户输入的关键字进行 POI 搜索，并返回相关的信息"""
    try:
        data = _request_json(
            "/v3/place/text",
            params={"keywords": keywords, "city": city, "citylimit": citylimit},
        )
        error = _status_error(data, label="Text Search")
        if error is not None:
            return {"error": error}
            
        suggestion_cities = []
        if data.get("suggestion", {}).get("cities"):
            for city in data["suggestion"]["cities"]:
                suggestion_cities.append({"name": city.get("name")})
                
        pois = []
        for poi in data.get("pois", []):
            pois.append({
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "typecode": poi.get("typecode")
            })
            
        return {
            "suggestion": {
                "keywords": data.get("suggestion", {}).get("keywords"),
                "cities": suggestion_cities
            },
            "pois": pois
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_around_search(location: str, radius: str = "1000", keywords: str = "") -> Dict[str, Any]:
    """周边搜，根据用户传入关键词以及坐标location，搜索出radius半径范围的POI"""
    try:
        data = _request_json(
            "/v3/place/around",
            params={"location": location, "radius": radius, "keywords": keywords},
        )
        error = _status_error(data, label="Around Search")
        if error is not None:
            return {"error": error}
            
        pois = []
        for poi in data.get("pois", []):
            pois.append({
                "id": poi.get("id"),
                "name": poi.get("name"),
                "address": poi.get("address"),
                "typecode": poi.get("typecode")
            })
            
        return {"pois": pois}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def maps_search_detail(id: str) -> Dict[str, Any]:
    """查询关键词搜或者周边搜获取到的POI ID的详细信息"""
    try:
        data = _request_json("/v3/place/detail", params={"id": id})
        error = _status_error(data, label="Get poi detail")
        if error is not None:
            return {"error": error}
            
        if not data.get("pois"):
            return {"error": "No POI found"}
            
        poi = data["pois"][0]
        result = {
            "id": poi.get("id"),
            "name": poi.get("name"),
            "location": poi.get("location"),
            "address": poi.get("address"),
            "business_area": poi.get("business_area"),
            "city": poi.get("cityname"),
            "type": poi.get("type"),
            "alias": poi.get("alias")
        }
        
        # Add biz_ext data if available
        if poi.get("biz_ext"):
            result.update(poi["biz_ext"])
            
        return result
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}


def _required_str(args: Dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required argument: {key}")
    return value.strip()


def _optional_str(args: Dict[str, Any], key: str) -> Optional[str]:
    value = args.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _route_arg_docs(*, transit: bool = False) -> Dict[str, str]:
    docs = {
        "origin_address": "起点地址；与 destination_address 一起传时优先走地址版。",
        "destination_address": "终点地址；与 origin_address 一起传时优先走地址版。",
        "origin_city": "起点城市；建议显式提供以提高地址解析准确性。",
        "destination_city": "终点城市；建议显式提供以提高地址解析准确性。",
        "origin": "起点坐标，格式“经度,纬度”；仅在不用地址版时传。",
        "destination": "终点坐标，格式“经度,纬度”；仅在不用地址版时传。",
    }
    if transit:
        docs["origin_city"] = "起点城市；地址版和跨城场景都建议显式提供。"
        docs["destination_city"] = "终点城市；地址版和跨城场景都建议显式提供。"
    return docs


def _build_command_registry() -> List[CommandAction]:
    return [
        CommandAction(
            command="geo",
            resource="address",
            action="resolve",
            summary="将结构化地址解析为经纬度，适合地点确认、酒店/景点纠偏和路线规划前校验。",
            raw_tools=("maps_geo",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/georegeo",
            arg_docs={
                "address": "结构化地址或地标名称，例如“杭州市西湖区灵隐路法云弄1号”。",
                "city": "可选城市，用于提高地理编码准确性。",
            },
            use_cases=(
                "在行程开始前把模糊地点名解析成可用于 POI 和路线规划的坐标。",
                "对酒店、景点、车站等候选地点做纠偏与同名消歧。",
            ),
            examples=(
                {"address": "杭州市西湖区灵隐路法云弄1号", "city": "杭州"},
            ),
            acceptance_hint="先执行地址解析，再把返回的坐标接给 `route.*.plan` 或 `poi.around.search`。",
            impl_refs=("amap_mcp_server/server.py::maps_geo",),
            runner=lambda args: maps_geo(address=_required_str(args, "address"), city=_optional_str(args, "city")),
        ),
        CommandAction(
            command="geo",
            resource="location",
            action="reverse",
            summary="将经纬度反查为行政区划与地址上下文，适合校验坐标归属地。",
            raw_tools=("maps_regeocode",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/georegeo",
            arg_docs={
                "location": "经纬度坐标，格式为“经度,纬度”。",
            },
            use_cases=(
                "校验来自外部系统的坐标是否真的落在目标城市或景区。",
                "给路线或 POI 结果补充行政区划上下文。",
            ),
            examples=(
                {"location": "120.130663,30.240018"},
            ),
            acceptance_hint="可用 `poi.keyword.search` 找到地点后，再用其坐标做一次反查验证。",
            impl_refs=("amap_mcp_server/server.py::maps_regeocode",),
            runner=lambda args: maps_regeocode(location=_required_str(args, "location")),
        ),
        CommandAction(
            command="geo",
            resource="ip",
            action="locate",
            summary="根据 IP 反查大致地理位置，适合城市级定位，不适合精确路线规划。",
            raw_tools=("maps_ip_location",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/ipconfig",
            arg_docs={
                "ip": "待查询的 IPv4 地址。",
            },
            use_cases=(
                "在没有显式城市信息时做粗粒度城市猜测。",
                "根据用户来源 IP 预填默认城市，再交给后续 POI 或天气查询细化。",
            ),
            examples=(
                {"ip": "1.2.3.4"},
            ),
            acceptance_hint="城市级定位只适合作为默认值，不应直接用于精确路线规划。",
            impl_refs=("amap_mcp_server/server.py::maps_ip_location",),
            runner=lambda args: maps_ip_location(ip=_required_str(args, "ip")),
        ),
        CommandAction(
            command="weather",
            resource="city",
            action="get",
            summary="查询城市天气，适合给行程附加天气风险提示。",
            raw_tools=("maps_weather",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/weatherinfo",
            arg_docs={
                "city": "城市名称或 adcode。",
            },
            use_cases=(
                "给每日行程补充天气风险提示。",
                "比较多个候选城市的天气条件，辅助出行建议。",
            ),
            examples=(
                {"city": "杭州"},
            ),
            acceptance_hint="通常在行程骨架稳定后再查询天气，避免过早请求。",
            impl_refs=("amap_mcp_server/server.py::maps_weather",),
            runner=lambda args: maps_weather(city=_required_str(args, "city")),
        ),
        CommandAction(
            command="poi",
            resource="keyword",
            action="search",
            summary="按关键词做 POI 搜索，适合搜景点、商圈、酒店、美食等候选列表。",
            raw_tools=("maps_text_search",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/search",
            arg_docs={
                "keywords": "搜索关键词，例如“西湖 景点”或“北京南站 酒店”。",
                "city": "可选城市名称，建议在行程场景中尽量提供。",
                "citylimit": "是否限制在指定城市内搜索，字符串 true/false，默认 false。",
            },
            use_cases=(
                "按城市和主题筛出候选景点、商圈、酒店或餐厅。",
                "在 trip-planner 中为某一站点生成备选地点列表。",
            ),
            examples=(
                {"keywords": "西湖 景点", "city": "杭州", "citylimit": "true"},
            ),
            acceptance_hint="如果结果过宽，先补 `city` 或改用 `poi.around.search` 收窄范围。",
            impl_refs=("amap_mcp_server/server.py::maps_text_search",),
            runner=lambda args: maps_text_search(
                keywords=_required_str(args, "keywords"),
                city=_optional_str(args, "city") or "",
                citylimit=_optional_str(args, "citylimit") or "false",
            ),
        ),
        CommandAction(
            command="poi",
            resource="around",
            action="search",
            summary="围绕一个中心点搜周边 POI，适合酒店周边、美食周边、车站周边筛选。",
            raw_tools=("maps_around_search",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/search",
            arg_docs={
                "location": "中心点经纬度，格式为“经度,纬度”。",
                "radius": "搜索半径（米），默认 1000。",
                "keywords": "可选关键词，例如“咖啡”“酒店”“地铁站”。",
            },
            use_cases=(
                "围绕酒店、景点或车站找周边餐饮与配套设施。",
                "围绕行程中的锚点做局部探索，而不是全城搜索。",
            ),
            examples=(
                {"location": "120.130663,30.240018", "radius": "1500", "keywords": "酒店"},
            ),
            acceptance_hint="通常先用 `geo.address.resolve` 或 `poi.keyword.search` 拿到中心点，再做 around 搜索。",
            impl_refs=("amap_mcp_server/server.py::maps_around_search",),
            runner=lambda args: maps_around_search(
                location=_required_str(args, "location"),
                radius=_optional_str(args, "radius") or "1000",
                keywords=_optional_str(args, "keywords") or "",
            ),
        ),
        CommandAction(
            command="poi",
            resource="place",
            action="detail",
            summary="按 POI ID 查看详细信息，适合在候选确认后补地址、营业区和细节。",
            raw_tools=("maps_search_detail",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/search",
            arg_docs={
                "id": "POI ID，一般来自 keyword/around 搜索结果。",
            },
            use_cases=(
                "对候选 POI 进一步补充地址、商圈和业务扩展信息。",
                "在 agent 已选定某个候选地点后做最终确认。",
            ),
            examples=(
                {"id": "B0FFG7JQ2E"},
            ),
            acceptance_hint="该 action 通常紧跟在 `poi.keyword.search` 或 `poi.around.search` 之后。",
            impl_refs=("amap_mcp_server/server.py::maps_search_detail",),
            runner=lambda args: maps_search_detail(id=_required_str(args, "id")),
        ),
        CommandAction(
            command="route",
            resource="bicycling",
            action="plan",
            summary="规划骑行路线。优先使用地址版参数，只有明确需要时再传坐标。",
            raw_tools=("maps_bicycling_by_address", "maps_bicycling_by_coordinates"),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/direction",
            arg_docs=_route_arg_docs(),
            use_cases=(
                "规划景点之间的低碳短距离通勤。",
                "在城市游场景里对比步行与骑行路线成本。",
            ),
            examples=(
                {"origin_address": "西湖文化广场", "destination_address": "武林广场", "origin_city": "杭州", "destination_city": "杭州"},
            ),
            acceptance_hint="默认先传地址版参数；只有坐标已明确且不需要再次解析时再传 `origin` / `destination`。",
            impl_refs=(
                "amap_mcp_server/server.py::_run_route_bicycling",
                "amap_mcp_server/server.py::maps_bicycling_by_address",
                "amap_mcp_server/server.py::maps_bicycling_by_coordinates",
            ),
            runner=_run_route_bicycling,
        ),
        CommandAction(
            command="route",
            resource="walking",
            action="plan",
            summary="规划步行路线。优先使用地址版参数，只有明确需要时再传坐标。",
            raw_tools=("maps_direction_walking_by_address", "maps_direction_walking_by_coordinates"),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/direction",
            arg_docs=_route_arg_docs(),
            use_cases=(
                "规划园区、景区、商圈内的短距离步行路线。",
                "为行程卡片补充步行时间和分段导航。",
            ),
            examples=(
                {"origin_address": "灵隐寺", "destination_address": "飞来峰", "origin_city": "杭州", "destination_city": "杭州"},
            ),
            acceptance_hint="景区内步行路线建议先用地址版，方便 agent 在输出中带回原始地址。",
            impl_refs=(
                "amap_mcp_server/server.py::_run_route_walking",
                "amap_mcp_server/server.py::maps_direction_walking_by_address",
                "amap_mcp_server/server.py::maps_direction_walking_by_coordinates",
            ),
            runner=_run_route_walking,
        ),
        CommandAction(
            command="route",
            resource="driving",
            action="plan",
            summary="规划驾车路线。优先使用地址版参数，只有明确需要时再传坐标。",
            raw_tools=("maps_direction_driving_by_address", "maps_direction_driving_by_coordinates"),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/direction",
            arg_docs=_route_arg_docs(),
            use_cases=(
                "规划机场、车站与酒店之间的驾车或打车路线。",
                "评估多个景点之间的车程成本。",
            ),
            examples=(
                {"origin_address": "杭州东站", "destination_address": "西湖风景名胜区", "origin_city": "杭州", "destination_city": "杭州"},
            ),
            acceptance_hint="如果要给用户呈现行程时长和距离，优先选驾车路线再对比公共交通。",
            impl_refs=(
                "amap_mcp_server/server.py::_run_route_driving",
                "amap_mcp_server/server.py::maps_direction_driving_by_address",
                "amap_mcp_server/server.py::maps_direction_driving_by_coordinates",
            ),
            runner=_run_route_driving,
        ),
        CommandAction(
            command="route",
            resource="transit",
            action="plan",
            summary="规划公共交通路线。优先使用地址版参数；跨城时必须提供起终点城市。",
            raw_tools=("maps_direction_transit_integrated_by_address", "maps_direction_transit_integrated_by_coordinates"),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/direction",
            arg_docs=_route_arg_docs(transit=True),
            use_cases=(
                "规划城市内公共交通换乘方案。",
                "在跨城场景里比较高铁、公交、地铁等综合通勤成本。",
            ),
            examples=(
                {"origin_address": "杭州东站", "destination_address": "西湖风景名胜区", "origin_city": "杭州", "destination_city": "杭州"},
            ),
            acceptance_hint="公共交通规划对城市参数更敏感；跨城场景务必同时传 `origin_city` 和 `destination_city`。",
            impl_refs=(
                "amap_mcp_server/server.py::_run_route_transit",
                "amap_mcp_server/server.py::maps_direction_transit_integrated_by_address",
                "amap_mcp_server/server.py::maps_direction_transit_integrated_by_coordinates",
            ),
            runner=_run_route_transit,
        ),
        CommandAction(
            command="route",
            resource="distance",
            action="measure",
            summary="测量起终点距离，可选驾车、步行或球面距离模式。",
            raw_tools=("maps_distance",),
            docs_url="https://lbs.amap.com/api/webservice/guide/api/distance",
            arg_docs={
                "origins": "起点坐标，可为一个或多个，多个时用竖线分隔。",
                "destination": "终点坐标，格式“经度,纬度”。",
                "type": "距离类型，默认 1；具体模式见高德距离测量文档。",
            },
            use_cases=(
                "快速比较多个候选地点到同一终点的距离。",
                "在正式路线规划前做粗粒度筛选。",
            ),
            examples=(
                {"origins": "120.130663,30.240018", "destination": "120.155070,30.274085", "type": "1"},
            ),
            acceptance_hint="多个起点可用 `|` 拼接，适合先粗筛再进入详细路线规划。",
            impl_refs=("amap_mcp_server/server.py::maps_distance",),
            runner=lambda args: maps_distance(
                origins=_required_str(args, "origins"),
                destination=_required_str(args, "destination"),
                type=_optional_str(args, "type") or "1",
            ),
        ),
    ]


def _run_route_bicycling(args: Dict[str, Any]) -> Dict[str, Any]:
    if _optional_str(args, "origin_address") and _optional_str(args, "destination_address"):
        return maps_bicycling_by_address(
            origin_address=_required_str(args, "origin_address"),
            destination_address=_required_str(args, "destination_address"),
            origin_city=_optional_str(args, "origin_city"),
            destination_city=_optional_str(args, "destination_city"),
        )
    return maps_bicycling_by_coordinates(
        origin_coordinates=_required_str(args, "origin"),
        destination_coordinates=_required_str(args, "destination"),
    )


def _run_route_walking(args: Dict[str, Any]) -> Dict[str, Any]:
    if _optional_str(args, "origin_address") and _optional_str(args, "destination_address"):
        return maps_direction_walking_by_address(
            origin_address=_required_str(args, "origin_address"),
            destination_address=_required_str(args, "destination_address"),
            origin_city=_optional_str(args, "origin_city"),
            destination_city=_optional_str(args, "destination_city"),
        )
    return maps_direction_walking_by_coordinates(
        origin=_required_str(args, "origin"),
        destination=_required_str(args, "destination"),
    )


def _run_route_driving(args: Dict[str, Any]) -> Dict[str, Any]:
    if _optional_str(args, "origin_address") and _optional_str(args, "destination_address"):
        return maps_direction_driving_by_address(
            origin_address=_required_str(args, "origin_address"),
            destination_address=_required_str(args, "destination_address"),
            origin_city=_optional_str(args, "origin_city"),
            destination_city=_optional_str(args, "destination_city"),
        )
    return maps_direction_driving_by_coordinates(
        origin=_required_str(args, "origin"),
        destination=_required_str(args, "destination"),
    )


def _run_route_transit(args: Dict[str, Any]) -> Dict[str, Any]:
    origin_city = _optional_str(args, "origin_city")
    destination_city = _optional_str(args, "destination_city")
    if _optional_str(args, "origin_address") and _optional_str(args, "destination_address"):
        return maps_direction_transit_integrated_by_address(
            origin_address=_required_str(args, "origin_address"),
            destination_address=_required_str(args, "destination_address"),
            origin_city=_required_str(args, "origin_city"),
            destination_city=_required_str(args, "destination_city"),
        )
    return maps_direction_transit_integrated_by_coordinates(
        origin=_required_str(args, "origin"),
        destination=_required_str(args, "destination"),
        city=origin_city or _required_str(args, "origin_city"),
        cityd=destination_city or _required_str(args, "destination_city"),
    )


COMMAND_ACTIONS = _build_command_registry()
COMMAND_INDEX = {(item.command, item.resource, item.action): item for item in COMMAND_ACTIONS}
TARGET_INDEX = {item.target: item for item in COMMAND_ACTIONS}


def _action_cite(action: CommandAction) -> Dict[str, Any]:
    return {
        "help_target": action.target,
        "raw_tool": " | ".join(action.raw_tools),
        "raw_tools": list(action.raw_tools),
        "docs_url": action.docs_url,
        "impl_refs": list(action.impl_refs),
    }


def _action_payload(action: CommandAction) -> Dict[str, Any]:
    return {
        "target": action.target,
        "summary": action.summary,
        "use_cases": list(action.use_cases),
        "arguments": action.arg_docs,
        "examples": list(action.examples),
        "acceptance_hint": action.acceptance_hint,
        **_action_cite(action),
    }


def _matching_actions(target: str | None) -> List[CommandAction]:
    normalized = (target or "").strip().lower()
    if not normalized:
        return COMMAND_ACTIONS
    parts = [part.strip().lower() for part in normalized.split(".") if part.strip()]
    if len(parts) == 1:
        return [item for item in COMMAND_ACTIONS if item.command == parts[0]]
    if len(parts) == 2:
        return [item for item in COMMAND_ACTIONS if item.command == parts[0] and item.resource == parts[1]]
    if len(parts) == 3:
        action = TARGET_INDEX.get(".".join(parts))
        return [action] if action is not None else []
    return []


def _summarize_run_result(action: CommandAction, data: Dict[str, Any]) -> str:
    if "error" in data:
        return str(data["error"])
    if "pois" in data and isinstance(data["pois"], list):
        return f"found {len(data['pois'])} POI candidates"
    if "results" in data and isinstance(data["results"], list):
        return f"measured {len(data['results'])} distance result(s)"
    if "return" in data and isinstance(data["return"], list):
        return f"resolved {len(data['return'])} geocode candidate(s)"
    route = data.get("route")
    if isinstance(route, dict):
        if isinstance(route.get("paths"), list):
            return f"planned {len(route['paths'])} {action.resource} route option(s)"
        if isinstance(route.get("transits"), list):
            return f"planned {len(route['transits'])} transit option(s)"
    if "data" in data and isinstance(data["data"], dict) and isinstance(data["data"].get("paths"), list):
        return f"planned {len(data['data']['paths'])} bicycling route option(s)"
    if action.target == "weather.city.get":
        city = data.get("city")
        count = len(data.get("forecasts") or [])
        return f"loaded {count} weather forecast item(s) for {city or 'city'}"
    return action.summary


def _suggestions_for_error(action: Optional[CommandAction], error: str) -> List[str]:
    lower = error.lower()
    suggestions: List[str] = []
    if (
        "amap_maps_api_key" in lower
        or "invalid user key" in lower
        or "invalid_user_key" in lower
        or "user key" in lower
    ):
        suggestions.append("检查当前 shell 是否已设置有效的 AMAP_MAPS_API_KEY。")
    if "daily_query_over_limit" in lower or "too many requests" in lower or "quota" in lower:
        suggestions.append("检查高德 key 配额是否超限，必要时切换 key 或降低请求频率。")
    if "no geocoding results" in lower:
        suggestions.append("补充更精确的地址或城市信息，再重新执行地址解析。")
    if "origin_city" in lower or "destination_city" in lower:
        suggestions.append("公共交通规划建议显式提供 origin_city 和 destination_city。")
    if action is not None and action.command == "poi":
        suggestions.append("如果关键词过宽，可补 city 或改成 around 搜索缩小范围。")
    if not suggestions:
        suggestions.append("先用 help 查看该 action 的参数要求，再补齐必要字段。")
    return suggestions


def list_command_catalog(target: str = "") -> Dict[str, Any]:
    actions = _matching_actions(target)
    if target and not actions:
        return {
            "ok": False,
            "target": target,
            "error": f"unknown target: {target}",
            "suggestions": ["先不带 target 调用 ls 查看全量 command。"],
        }

    normalized = (target or "").strip().lower()
    parts = [part.strip() for part in normalized.split(".") if part.strip()]
    if not parts:
        commands = sorted({item.command for item in COMMAND_ACTIONS})
        return {
            "ok": True,
            "level": "command",
            "commands": commands,
            "summary": f"{len(commands)} commands available",
        }
    if len(parts) == 1:
        resources = sorted({item.resource for item in actions})
        return {
            "ok": True,
            "target": parts[0],
            "level": "resource",
            "resources": resources,
            "summary": f"{parts[0]} has {len(resources)} resources",
        }
    if len(parts) == 2:
        return {
            "ok": True,
            "target": ".".join(parts),
            "level": "action",
            "actions": [
                {
                    "action": item.action,
                    "summary": item.summary,
                    **_action_cite(item),
                }
                for item in actions
            ],
            "summary": f"{parts[0]}.{parts[1]} has {len(actions)} action(s)",
        }
    item = actions[0]
    return {
        "ok": True,
        "target": item.target,
        "level": "action",
        **_action_payload(item),
    }


def get_action_help(target: str, field: str = "") -> Dict[str, Any]:
    item = TARGET_INDEX.get(target.strip().lower())
    if item is None:
        return {
            "ok": False,
            "target": target,
            "error": f"unknown help target: {target}",
            "suggestions": ["先用 ls 找到正确的 command.resource.action。"],
        }
    if field:
        field_key = field.strip()
        doc = item.arg_docs.get(field_key)
        if doc is None:
            return {
                "ok": False,
                "target": item.target,
                "field": field_key,
                "error": f"unknown field: {field_key}",
                "suggestions": ["不传 field 再调用 help，可查看该 action 的全部参数。"],
                **_action_cite(item),
            }
        return {
            "ok": True,
            "target": item.target,
            "field": field_key,
            "description": doc,
            "acceptance_hint": item.acceptance_hint,
            **_action_cite(item),
        }
    return {
        "ok": True,
        **_action_payload(item),
    }


def _run_command_action(item: CommandAction, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        data = item.runner(payload)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)
        return {
            "ok": False,
            "target": item.target,
            "error": error,
            "suggestions": _suggestions_for_error(item, error),
            "acceptance_hint": item.acceptance_hint,
            **_action_cite(item),
        }
    if not isinstance(data, dict):
        return {
            "ok": False,
            "target": item.target,
            "error": "runner returned non-dict result",
            "suggestions": _suggestions_for_error(item, "runner returned non-dict result"),
            "acceptance_hint": item.acceptance_hint,
            **_action_cite(item),
        }
    if "error" in data:
        error = str(data["error"])
        return {
            "ok": False,
            "target": item.target,
            "error": error,
            "suggestions": _suggestions_for_error(item, error),
            "acceptance_hint": item.acceptance_hint,
            **_action_cite(item),
        }
    return {
        "ok": True,
        "target": item.target,
        "summary": _summarize_run_result(item, data),
        "data": data,
        "use_cases": list(item.use_cases),
        "next": ["如需参数说明，可调用 help。", "如需查看同类能力，可调用 ls。"],
        "acceptance_hint": item.acceptance_hint,
        **_action_cite(item),
    }


def run_command(command: str, resource: str, action: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    item = COMMAND_INDEX.get((command.strip().lower(), resource.strip().lower(), action.strip().lower()))
    if item is None:
        target = ".".join([command.strip(), resource.strip(), action.strip()])
        return {
            "ok": False,
            "target": target,
            "error": f"unknown command target: {target}",
            "suggestions": ["先调用 ls 或 help 确认可用 target。"],
        }
    payload = args if isinstance(args, dict) else {}
    return _run_command_action(item, payload)


def run_command_target(target: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    item = TARGET_INDEX.get(target.strip().lower())
    if item is None:
        return {
            "ok": False,
            "target": target,
            "error": f"unknown command target: {target}",
            "suggestions": ["先调用 ls 或 help 确认可用 target。"],
        }
    payload = args if isinstance(args, dict) else {}
    return _run_command_action(item, payload)


def explain_error(target: str, error: str) -> Dict[str, Any]:
    item = TARGET_INDEX.get(target.strip().lower())
    suggestions = _suggestions_for_error(item, error)
    payload = {
        "ok": True,
        "target": target,
        "error": error,
        "summary": "Explained likely cause and next actions.",
        "suggestions": suggestions,
    }
    if item is not None:
        payload.update(_action_cite(item))
    return payload


def catalog_snapshot() -> Dict[str, Any]:
    return {
        "commands": sorted({item.command for item in COMMAND_ACTIONS}),
        "actions": [_action_payload(item) for item in COMMAND_ACTIONS],
    }


def render_commands_reference_markdown() -> str:
    sections = [
        "<!-- Generated from `amap_mcp_server.server.COMMAND_ACTIONS`. -->",
        "# Command Reference",
        "",
        "默认推荐 agent 先通过 `ls -> help -> run -> explain` 使用高德能力。",
        "raw `maps_*` 工具仍然保留用于兼容与调试，但不是默认主路径。",
        "",
    ]
    commands = sorted({item.command for item in COMMAND_ACTIONS})
    for command in commands:
        sections.append(f"## `{command}`")
        sections.append("")
        command_actions = [item for item in COMMAND_ACTIONS if item.command == command]
        resources = sorted({item.resource for item in command_actions})
        for resource in resources:
            sections.append(f"### `{command}.{resource}`")
            sections.append("")
            for item in [entry for entry in command_actions if entry.resource == resource]:
                sections.append(f"#### `{item.target}`")
                sections.append("")
                sections.append(item.summary)
                sections.append("")
                sections.append("适用场景：")
                for use_case in item.use_cases:
                    sections.append(f"- {use_case}")
                sections.append("")
                sections.append("参数：")
                for field_name, doc in item.arg_docs.items():
                    sections.append(f"- `{field_name}`: {doc}")
                sections.append("")
                sections.append("示例：")
                for example in item.examples:
                    sections.append("```json")
                    sections.append(json.dumps(example, ensure_ascii=False, indent=2))
                    sections.append("```")
                sections.append("")
                sections.append("Cites：")
                sections.append(f"- raw tools: {', '.join(f'`{tool}`' for tool in item.raw_tools)}")
                sections.append(f"- docs: {item.docs_url}")
                for impl_ref in item.impl_refs:
                    sections.append(f"- impl: `{impl_ref}`")
                sections.append(f"- acceptance: {item.acceptance_hint}")
                sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def ls(target: str = "") -> Dict[str, Any]:
    """列出高德命令面下可用的 command / resource / action。"""
    return list_command_catalog(target)


def help(target: str, field: str = "") -> Dict[str, Any]:
    """查看命令面某个 target 或参数字段的说明。"""
    return get_action_help(target, field)


def run(command: str, resource: str, action: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """执行高德命令面 action，统一返回 summary/data/cite。"""
    return run_command(command, resource, action, args)


def explain(target: str, error: str) -> Dict[str, Any]:
    """解释错误、常见限制和下一步建议。"""
    return explain_error(target, error)


RAW_TOOL_FUNCTIONS: tuple[Callable[..., Dict[str, Any]], ...] = (
    maps_regeocode,
    maps_geo,
    maps_ip_location,
    maps_weather,
    maps_bicycling_by_address,
    maps_bicycling_by_coordinates,
    maps_direction_walking_by_address,
    maps_direction_walking_by_coordinates,
    maps_direction_driving_by_address,
    maps_direction_driving_by_coordinates,
    maps_direction_transit_integrated_by_address,
    maps_direction_transit_integrated_by_coordinates,
    maps_distance,
    maps_text_search,
    maps_around_search,
    maps_search_detail,
)


FACADE_TOOL_FUNCTIONS: tuple[Callable[..., Dict[str, Any]], ...] = (
    ls,
    help,
    run,
    explain,
)
