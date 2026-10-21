import math

import requests
from langsmith import traceable

import config

NAVI_URL = "https://apis-navi.kakaomobility.com/v1/directions"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
ODSAY_URL = "https://api.odsay.com/v1/api/searchPubTransPathT"

# Open-Meteo WMO 날씨 코드 → (아이콘, 설명)
WEATHER_CODES = {
    0: ("☀️", "맑음"), 1: ("🌤️", "대체로 맑음"), 2: ("⛅", "구름 조금"), 3: ("☁️", "흐림"),
    45: ("🌫️", "안개"), 48: ("🌫️", "안개"),
    51: ("🌦️", "이슬비"), 53: ("🌦️", "이슬비"), 55: ("🌦️", "이슬비"),
    61: ("🌧️", "비"), 63: ("🌧️", "비"), 65: ("🌧️", "강한 비"),
    71: ("🌨️", "눈"), 73: ("🌨️", "눈"), 75: ("❄️", "강한 눈"),
    80: ("🌦️", "소나기"), 81: ("🌦️", "소나기"), 82: ("⛈️", "강한 소나기"),
    95: ("⛈️", "뇌우"), 96: ("⛈️", "뇌우"), 99: ("⛈️", "뇌우"),
}


def distance_km(a: dict, b: dict) -> float:
    """두 장소(x=경도, y=위도) 사이 직선거리."""
    lon1, lat1, lon2, lat2 = map(math.radians, (a["x"], a["y"], b["x"], b["y"]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + (
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


def walk_minutes(km: float) -> int:
    # 직선거리 × 1.3(길 굽음) ÷ 시속 4.8km
    return max(1, round(km * 1.3 / 4.8 * 60))


def car_minutes(a: dict, b: dict, km: float) -> tuple[int, bool]:
    """(분, 실제값 여부). 카카오 길찾기 실패 시 거리 기반 예상값."""
    try:
        r = requests.get(
            NAVI_URL,
            headers={"Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}"},
            params={"origin": f"{a['x']},{a['y']}", "destination": f"{b['x']},{b['y']}"},
            timeout=5,
        )
        route = r.json()["routes"][0]
        if route.get("result_code") == 0:
            return max(1, round(route["summary"]["duration"] / 60)), True
    except Exception:
        pass
    speed = 30 if km < 10 else 50
    return max(1, round(km * 1.3 / speed * 60)), False


def transit(a: dict, b: dict) -> dict | None:
    """ODsay 대중교통 길찾기. 키가 없거나 버스·지하철을 안 타는 경로면 None.
    {"min": 총 소요 분, "text": "버스 1001 → 지하철 수도권 2호선"}"""
    if not config.ODSAY_API_KEY:
        return None
    try:
        r = requests.get(
            ODSAY_URL,
            params={
                "apiKey": config.ODSAY_API_KEY,
                "SX": a["x"], "SY": a["y"], "EX": b["x"], "EY": b["y"],
                "OPT": 0, "SearchType": 0,
            },
            timeout=5,
        )
        path = r.json()["result"]["path"][0]
    except Exception:
        return None
    steps = []
    for sp in path.get("subPath", []):
        lane = (sp.get("lane") or [{}])[0]
        if sp.get("trafficType") == 1 and lane.get("name"):  # 지하철
            steps.append(f"지하철 {lane['name']}")
        elif sp.get("trafficType") == 2 and lane.get("busNo"):  # 버스
            steps.append(f"버스 {lane['busNo']}")
    if not steps:  # 도보만 있는 경로
        return None
    return {"min": path["info"]["totalTime"], "text": " → ".join(steps)}


@traceable(name="route_leg", run_type="tool")
def leg(a: dict, b: dict) -> dict:
    km = distance_km(a, b)
    car, exact = car_minutes(a, b, km)
    return {
        "km": round(km * 1.3, 1),
        "walk": walk_minutes(km),
        "car": car,
        "car_exact": exact,
        "transit": transit(a, b),
    }


@traceable(name="weather_forecast", run_type="tool")
def forecast(
    lat: float, lon: float, start: str = "", end: str = "", days: int = 3
) -> list[dict]:
    """목적지 좌표의 날씨. start/end(YYYY-MM-DD)가 있으면 그 기간, 없으면 오늘부터 며칠.
    예보 범위(약 16일) 밖이거나 실패하면 빈 목록."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max",
        "timezone": "Asia/Seoul",
    }
    if start and end:
        params.update(start_date=start, end_date=end)
    else:
        params["forecast_days"] = days
    try:
        r = requests.get(WEATHER_URL, params=params, timeout=5)
        d = r.json()["daily"]
    except Exception:
        return []
    out = []
    for i, date in enumerate(d["time"]):
        icon, text = WEATHER_CODES.get(d["weather_code"][i], ("🌡️", "정보 없음"))
        out.append(
            {
                "date": date,
                "icon": icon,
                "text": text,
                "tmax": d["temperature_2m_max"][i],
                "tmin": d["temperature_2m_min"][i],
                "rain": d["precipitation_probability_max"][i],
            }
        )
    return out
