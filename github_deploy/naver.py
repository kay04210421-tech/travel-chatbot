import html
import re
from urllib.parse import quote

import requests

import config

BLOG_URL = "https://openapi.naver.com/v1/search/blog.json"


def map_link(query: str) -> str:
    """네이버 지도 검색 링크. 별점·방문자 리뷰는 이 페이지에서 확인한다."""
    return f"https://map.naver.com/p/search/{quote(query)}"


def blog_search_link(query: str) -> str:
    return f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={quote(query + ' 후기')}"


def _clean(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def has_blog_api() -> bool:
    return bool(config.NAVER_CLIENT_ID and config.NAVER_CLIENT_SECRET)


def search_blogs(query: str, count: int = 3) -> list[dict]:
    """네이버 블로그 검색 API. 키가 없거나 실패하면 빈 목록을 돌려준다."""
    if not has_blog_api():
        return []
    try:
        resp = requests.get(
            BLOG_URL,
            headers={
                "X-Naver-Client-Id": config.NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": config.NAVER_CLIENT_SECRET,
            },
            params={"query": f"{query} 후기", "display": count, "sort": "sim"},
            timeout=5,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception:
        return []
    return [
        {
            "title": _clean(i.get("title", "")),
            "desc": _clean(i.get("description", "")),
            "link": i.get("link", ""),
            "blogger": _clean(i.get("bloggername", "")),
        }
        for i in items
    ]
