import requests
from langsmith import traceable

import config

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoError(Exception):
    """카카오 장소 검색 실패. 메시지에는 키를 넣지 않는다."""


def has_key() -> bool:
    return bool(config.KAKAO_REST_API_KEY)


@traceable(name="kakao_search", run_type="tool")  # 키는 헤더에만 있어 기록되지 않는다
def search(query: str, size: int = 4) -> list[dict]:
    try:
        resp = requests.get(
            URL,
            headers={"Authorization": f"KakaoAK {config.KAKAO_REST_API_KEY}"},
            params={"query": query, "size": size},
            timeout=5,
        )
    except requests.RequestException as e:
        raise KakaoError(f"네트워크 오류({type(e).__name__})") from None
    if resp.status_code != 200:
        raise KakaoError(f"HTTP {resp.status_code}")
    docs = [
        d
        for d in resp.json().get("documents", [])
        if not any(w in d.get("category_name", "") for w in ("주차장", "입출구", "화장실", "충전소", "편의점", "마트"))
    ]
    return [
        {
            "id": d.get("id", ""),
            "name": d.get("place_name", ""),
            "category": d.get("category_name", "").split(" > ")[-1],
            "is_food": d.get("category_group_code") == "FD6",
            "address": d.get("road_address_name") or d.get("address_name", ""),
            "phone": d.get("phone", ""),
            "url": d.get("place_url", ""),
            "x": float(d.get("x") or 0),
            "y": float(d.get("y") or 0),
        }
        for d in docs
    ]
