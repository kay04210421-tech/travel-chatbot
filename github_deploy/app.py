import html
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # numpy 메모리 할당 실패 방지 (지도 라이브러리가 사용)

import folium
import streamlit as st
from langsmith import traceable
import streamlit.components.v1 as components
from streamlit_folium import st_folium
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

import config
import kakao
import naver
import trip

st.set_page_config(page_title="여행 챗봇", page_icon="🧳")


class Plan(BaseModel):
    queries: list[str] = Field(default_factory=list, description="카카오 장소 검색어")
    itinerary: bool = Field(default=False, description="일정·코스를 짜 달라는 요청이면 true")
    start_date: str = Field(
        default="", description="여행 시작일 YYYY-MM-DD. 날짜를 말하지 않았으면 빈 문자열"
    )
    end_date: str = Field(default="", description="여행 종료일 YYYY-MM-DD. 없으면 빈 문자열")
    weather_places: list[str] = Field(
        default_factory=list,
        description="날씨·기온·비 여부를 묻는 질문이면 알고 싶은 지역 이름(예: 부산 동구 초량동)",
    )
    areas: list[str] = Field(
        default_factory=list,
        description="일정일 때 방문할 구·동네, 하루에 하나(예: 해운대, 광안리)",
    )


class Pick(BaseModel):
    name: str = Field(description="후보 장소 이름 (그대로)")
    reason: str = Field(description="한 줄 이유")


KINDS = ["식사", "카페", "실내", "실외"]


class Stop(BaseModel):
    time: str = Field(description="방문 시각, 예: 11:30")
    name: str = Field(description="후보 장소 이름 (그대로)")
    kind: Literal["식사", "카페", "실내", "실외"]
    note: str = Field(description="한 줄 설명")


class Day(BaseModel):
    title: str = Field(description="그날의 동네·테마만, 예: '해운대'. 날짜나 'N일차'는 쓰지 말 것")
    stops: list[Stop]


class PackGroup(BaseModel):
    group: str = Field(description="분류, 예: 필수품, 의류, 날씨 대비, 전자기기, 기타")
    items: list[str]


class TravelReply(BaseModel):
    answer: str = Field(description="사용자에게 보여줄 답변")
    picks: list[Pick] = Field(default_factory=list)
    days: list[Day] = Field(default_factory=list, description="일정 요청일 때만")
    packing: list[PackGroup] = Field(
        default_factory=list, description="일정 요청일 때만: 이 일정에 맞춘 준비물"
    )


CSS = """
<style>
.block-container { max-width: 780px; padding-top: 4.5rem; padding-bottom: 7rem; }
.hero { background: linear-gradient(135deg,#1f3a8a,#2f6fed); color:#fff;
        border-radius:20px; padding:22px 26px; margin:0 0 22px;
        box-shadow:0 6px 18px rgba(31,58,138,.25); }
.hero h1 { color:#fff; font-size:1.7rem; line-height:1.3; margin:0 0 6px; padding:0; }
.hero p { margin:0; opacity:.92; font-size:.95rem; line-height:1.5; }
div[data-testid="stChatMessage"] { padding:.9rem 1rem; border-radius:16px; margin-bottom:.6rem; }
/* 결과 카테고리 메뉴: 화면 오른쪽에 고정되어 어느 답변을 보든 따라온다 */
.st-key-catnav { position:fixed; right:1.2rem; top:6rem; z-index:99; width:9rem;
  background:#f4f7fd; border:1px solid #e3e8f0; border-radius:16px; padding:8px 12px;
  box-shadow:0 4px 14px rgba(31,58,138,.12); }
.st-key-catnav label { padding:4px 2px; }
.st-key-catnav label p { font-size:.95rem; font-weight:600; }
@media (max-width: 900px) {
  .st-key-catnav { left:0; right:0; top:3.2rem; width:auto; border-radius:0; padding:4px 10px; }
  .st-key-catnav div[role="radiogroup"] { flex-direction:row; flex-wrap:wrap; gap:4px 14px; }
}
/* 사이드바 모드 버튼 */
.st-key-mode_chat button, .st-key-mode_plan button {
  min-height:3.4rem; font-size:1.15rem; font-weight:700; border-radius:14px; }
.st-key-nav_home button { border-radius:12px; }
/* 첫 화면 */
.home-hero { text-align:center; padding:34px 10px 26px; }
.home-hero h1 { font-size:3rem; margin:0 0 10px; padding:0; color:#1f3a8a; }
.home-hero p { font-size:1.1rem; color:#556; margin:0; }
.mode-card { background:#fff; border:2px solid #e3e8f0; border-radius:22px;
  padding:30px 22px; text-align:center; min-height:230px; margin-bottom:10px;
  box-shadow:0 4px 14px rgba(31,58,138,.08); }
.mode-card .mc-icon { font-size:3rem; }
.mode-card .mc-title { font-size:1.6rem; font-weight:800; color:#1f3a8a; margin:6px 0 12px; }
.mode-card .mc-desc { font-size:1rem; color:#445; line-height:1.7; }
.st-key-home_chat button, .st-key-home_plan button {
  min-height:3.2rem; font-size:1.1rem; font-weight:700; border-radius:14px; }
.cards { display:flex; gap:12px; overflow-x:auto; padding:6px 2px 10px; }
.card { flex:0 0 280px; background:#fff; border:1px solid #e3e8f0; border-radius:16px;
        padding:14px; box-shadow:0 2px 8px rgba(31,58,138,.08); color:#1a2233; }
.card .name { font-weight:700; font-size:1.05rem; }
.card .area { color:#667; font-size:.8rem; margin-bottom:6px; }
.card .sum { font-size:.88rem; margin-bottom:10px; }
.card a.btn { display:block; text-align:center; background:#fee500; color:#191919 !important;
        text-decoration:none; border-radius:10px; padding:8px; font-weight:600;
        font-size:.88rem; margin-bottom:6px; }
.card a.btn.naver { background:#03c75a; color:#fff !important; }
.card a.btn.sub { background:#eef2fb; color:#1f3a8a !important; }
.card .blogs { border-top:1px solid #edf0f5; margin-top:8px; padding-top:8px; }
.card .blogs b { font-size:.8rem; color:#445; }
.card .blogs a { display:block; text-decoration:none; color:#1a2233; margin-top:6px; }
.card .blogs .t { font-size:.85rem; font-weight:600; }
.card .blogs .d { font-size:.76rem; color:#667; }
.day { margin:4px 0 14px; }
.dtitle { font-weight:700; font-size:1.02rem; margin-bottom:6px; }
.dhead { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; color:#fff;
  background:linear-gradient(135deg,#1f3a8a,#2f6fed); border-radius:14px;
  padding:12px 18px; margin:30px 0 12px; box-shadow:0 3px 10px rgba(31,58,138,.25); }
.day:first-child .dhead { margin-top:8px; }
.dhead .dnum { font-size:1.3rem; font-weight:800; }
.dhead .ddate { font-size:1.05rem; font-weight:700; opacity:.95; }
.dhead .dplace { margin-left:auto; font-size:.9rem; opacity:.9; }
.pack-wrap { display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:10px;
  margin-top:6px; }
.pack { background:#f8faff; border:1px solid #e3e8f0; border-radius:14px; padding:12px 14px;
  color:#1a2233; }
.pack .pg { font-weight:700; color:#1f3a8a; margin-bottom:4px; }
.pack ul { list-style:none; margin:0; padding:0; font-size:.88rem; line-height:1.7; }
.stop { background:#fff; border:1px solid #e3e8f0; border-radius:12px; padding:10px 12px;
        color:#1a2233; }
.stop .row { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.stop .time { font-weight:700; color:#1f3a8a; font-size:.88rem; }
.stop a.sname { font-weight:700; text-decoration:none; color:#1a2233; }
.stop .saddr { font-size:.76rem; color:#778; margin-top:2px; }
.stop .note { font-size:.84rem; margin-top:4px; }
.badge { font-size:.72rem; font-weight:700; padding:2px 8px; border-radius:20px; color:#fff; }
.k-식사 { background:#e8590c; } .k-카페 { background:#8d6e63; }
.k-실내 { background:#5f3dc4; } .k-실외 { background:#2b8a3e; }
.leg { margin:5px 0 5px 14px; padding-left:10px; border-left:3px dashed #c5cde0;
       font-size:.8rem; color:#556; }
.wrow { display:flex; align-items:center; gap:12px; background:#f4f7fd; border-radius:12px;
        padding:10px 14px; margin-bottom:8px; color:#1a2233; }
.wrow .wi { font-size:1.8rem; }
.wrow .wd { font-weight:700; }
.wrow .wt { font-size:.84rem; color:#445; }
div[data-testid="stHorizontalBlock"] button { background:#1f3a8a; color:#fff;
        border-radius:12px; border:0; }
div[data-testid="stHorizontalBlock"] button:hover { background:#2f6fed; color:#fff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

CHATS_FILE = Path(__file__).parent / "chats.json"


def load_chats() -> dict:
    try:
        data = json.loads(CHATS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_chats():
    try:
        saved = {k: v for k, v in st.session_state.chats.items() if v["messages"]}
        CHATS_FILE.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


CHAT_MODE = "💬 질문하기"
PLAN_MODE = "🗓 일정 짜기"


def new_chat():
    cid = datetime.now().strftime("%Y%m%d%H%M%S%f")
    st.session_state.chats[cid] = {"title": "새 채팅", "messages": []}
    st.session_state.cid = cid
    st.session_state.messages = st.session_state.chats[cid]["messages"]
    st.session_state.mode = CHAT_MODE


def switch_chat(cid, goto_chat=True):
    st.session_state.cid = cid
    st.session_state.messages = st.session_state.chats[cid]["messages"]
    if goto_chat:
        st.session_state.mode = CHAT_MODE


def delete_chat():
    st.session_state.chats.pop(st.session_state.cid, None)
    save_chats()
    if st.session_state.chats:
        switch_chat(max(st.session_state.chats))
    else:
        new_chat()


if "chats" not in st.session_state:
    st.session_state.chats = load_chats()
    if st.session_state.chats:
        switch_chat(max(st.session_state.chats))
    else:
        new_chat()
    st.session_state.mode = None  # 사이트를 처음 열면 첫 화면(모드 선택)부터 보여준다
if "pending" not in st.session_state:
    st.session_state.pending = None


def set_mode(mode):
    st.session_state.mode = mode


def go_home():
    st.session_state.mode = None


with st.sidebar:
    st.button(
        "🏠 처음 화면", key="nav_home", on_click=go_home, use_container_width=True
    )
    st.button(
        CHAT_MODE,
        key="mode_chat",
        on_click=set_mode,
        args=(CHAT_MODE,),
        type="primary" if st.session_state.mode == CHAT_MODE else "secondary",
        use_container_width=True,
    )
    st.button(
        PLAN_MODE,
        key="mode_plan",
        on_click=set_mode,
        args=(PLAN_MODE,),
        type="primary" if st.session_state.mode == PLAN_MODE else "secondary",
        use_container_width=True,
    )
    st.divider()
    if config.LANGSMITH_ON:
        st.caption(f"🔎 LangSmith 추적 켜짐 · 프로젝트 {config.LANGSMITH_PROJECT}")
    st.button("➕ 새 채팅", on_click=new_chat, use_container_width=True)
    st.markdown("**여행 기록**")
    for cid in sorted(st.session_state.chats, reverse=True):
        chat = st.session_state.chats[cid]
        if not chat["messages"] and cid != st.session_state.cid:
            continue
        is_cur = cid == st.session_state.cid
        st.button(
            ("▶ " if is_cur else "") + chat["title"],
            key=f"chat_{cid}",
            on_click=switch_chat,
            args=(cid,),
            use_container_width=True,
        )
    st.button("🗑 현재 채팅 삭제", on_click=delete_chat, use_container_width=True)


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def safe_url(u: str) -> str:
    return u if u.startswith(("https://", "http://")) else "#"


def naver_query(p: dict) -> str:
    """네이버 지도 검색어: '지역 가게이름' (동명 가게를 구분하려고 시·도를 앞에 붙인다)."""
    return f"{p['address'].split(' ')[0]} {p['name']}".strip()


def cards_html(places: list[dict]) -> str:
    out = ['<div class="cards">']
    for p in places:
        q = naver_query(p)
        out.append(
            f'<div class="card"><div class="name">{esc(p["name"])}</div>'
            f'<div class="area">{esc(p["category"])} · {esc(p["address"])}'
            f'{" · " + esc(p["phone"]) if p["phone"] else ""}</div>'
            f'<div class="sum">{esc(p["reason"])}</div>'
            f'<a class="btn" href="{esc(safe_url(p["url"]))}" target="_blank" rel="noopener">'
            "📍 카카오맵에서 보기</a>"
            f'<a class="btn naver" href="{esc(naver.map_link(q))}" target="_blank" '
            'rel="noopener">⭐ 네이버 별점·리뷰 보기</a>'
            f'<a class="btn sub" href="{esc(naver.blog_search_link(q))}" target="_blank" '
            'rel="noopener">📝 블로그 후기 더보기</a>'
        )
        if p["blogs"]:
            out.append('<div class="blogs"><b>블로그 리뷰</b>')
            for b in p["blogs"]:
                out.append(
                    f'<a href="{esc(safe_url(b["link"]))}" target="_blank" rel="noopener">'
                    f'<div class="t">{esc(b["title"])}</div>'
                    f'<div class="d">{esc(b["desc"][:70])}…</div></a>'
                )
            out.append("</div>")
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def day_name(d: dict) -> str:
    """'1일차 해운대' 같은 표시 이름. 예전 저장분은 제목만 쓴다."""
    return f"{d['label']} {d['title']}" if d.get("label") else d["title"]


def packing_html(packing: list[dict]) -> str:
    out = ['<div class="pack-wrap">']
    for g in packing:
        items = "".join(f"<li>☐ {esc(i)}</li>" for i in g["items"])
        out.append(f'<div class="pack"><div class="pg">{esc(g["group"])}</div><ul>{items}</ul></div>')
    out.append("</div>")
    return "".join(out)


def days_html(days: list[dict]) -> str:
    out = []
    for day in days:
        if day.get("label"):  # 'N일차 + 날짜 + 동네' 머리글
            date_html = f'<span class="ddate">{esc(day["date"])}</span>' if day.get("date") else ""
            head = (
                f'<div class="dhead"><span class="dnum">{esc(day["label"])}</span>'
                f'{date_html}<span class="dplace">📍 {esc(day["title"])}</span></div>'
            )
        else:  # 예전에 저장된 일정
            head = f'<div class="dtitle">{esc(day["title"])}</div>'
        out.append(f'<div class="day">{head}')
        for s in day["stops"]:
            lg = s.get("leg")
            if lg:
                car = f"{lg['car']}분" + ("" if lg["car_exact"] else "(예상)")
                far = " (멀어서 차량 추천)" if lg["walk"] > 40 else ""
                tr = lg.get("transit")
                tr_html = (
                    f' · 🚌 대중교통 {tr["min"]}분 ({esc(tr["text"])})' if tr else ""
                )
                out.append(
                    f'<div class="leg">🚶 도보 약 {lg["walk"]}분 · 🚗 자차 {car}{tr_html}'
                    f' · 약 {lg["km"]}km{far}</div>'
                )
            out.append(
                f'<div class="stop"><div class="row">'
                f'<span class="badge k-{esc(s["kind"])}">{esc(s["kind"])}</span>'
                f'<span class="time">{esc(s["time"])}</span>'
                f'<a class="sname" href="{esc(naver.map_link(naver_query(s)))}" '
                f'target="_blank" rel="noopener" title="네이버 지도에서 별점·리뷰 보기">'
                f'{esc(s["name"])} ⭐</a></div>'
                f'<div class="saddr">{esc(s["address"])}</div>'
                f'<div class="note">{esc(s["note"])}</div></div>'
            )
        out.append("</div>")
    return "".join(out)


def weather_html(weather: list[dict]) -> str:
    return "".join(
        f'<div class="wrow"><div class="wi">{w["icon"]}</div><div>'
        f'<div class="wd">{esc(w.get("label", ""))} {esc(w["date"])} · {esc(w["text"])}</div>'
        f'<div class="wt">📍 {esc(w.get("place", ""))}</div>'
        f'<div class="wt">{w["tmin"]:.0f}° ~ {w["tmax"]:.0f}° · 강수확률 {w["rain"]}%</div>'
        "</div></div>"
        for w in weather
    )


CAT_PLAN, CAT_MAP, CAT_WEATHER, CAT_PACK = "📅 일정", "🗺 지도", "🌤 날씨", "🎒 준비물"
CATEGORIES = [CAT_PLAN, CAT_MAP, "🍽 식사", "☕ 카페", "🏛 실내", "🌳 실외", CAT_WEATHER, CAT_PACK]
CATEGORY_KIND = {"🍽 식사": "식사", "☕ 카페": "카페", "🏛 실내": "실내", "🌳 실외": "실외"}
KIND_COLORS = {"식사": "#e8590c", "카페": "#8d6e63", "실내": "#5f3dc4", "실외": "#2b8a3e"}
DAY_LINE_COLORS = ["#1f3a8a", "#c2255c", "#0b7285", "#e67700", "#5f3dc4", "#2b8a3e", "#868e96"]


def map_view(days: list[dict], key: str):
    """날짜별 방문 장소를 번호 마커와 연결선으로 보여주는 지도."""
    sel = st.radio(
        "지도에 표시할 일정",
        ["전체"] + [day_name(d) for d in days],
        horizontal=True,
        key=f"mapday_{key}",
    )
    chosen = days if sel == "전체" else [d for d in days if day_name(d) == sel]
    pts = [(s["y"], s["x"]) for d in chosen for s in d["stops"] if s["x"] and s["y"]]
    if not pts:
        st.info("지도에 표시할 좌표가 없어요.")
        return
    m = folium.Map(location=pts[0], zoom_start=14, tiles="OpenStreetMap")
    for di, d in enumerate(chosen):
        stops = [s for s in d["stops"] if s["x"] and s["y"]]
        color = DAY_LINE_COLORS[di % len(DAY_LINE_COLORS)]
        if len(stops) > 1:
            folium.PolyLine(
                [(s["y"], s["x"]) for s in stops], color=color, weight=3, opacity=0.7,
                dash_array="6",
            ).add_to(m)
        for n, s in enumerate(stops, 1):
            popup = (
                f"<b>{esc(s['name'])}</b><br>{esc(day_name(d))} · {esc(s['time'])} · "
                f"{esc(s['kind'])}<br>{esc(s['address'])}<br>"
                f"<a href='{esc(naver.map_link(naver_query(s)))}' target='_blank'>"
                f"네이버 지도 별점·리뷰</a> · "
                f"<a href='{esc(safe_url(s['url']))}' target='_blank'>카카오맵</a>"
            )
            icon = folium.DivIcon(
                icon_size=(28, 28), icon_anchor=(14, 14),
                html=(
                    f"<div style='width:28px;height:28px;border-radius:50%;"
                    f"background:{KIND_COLORS.get(s['kind'], '#555')};color:#fff;"
                    f"border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);"
                    f"text-align:center;line-height:24px;font-weight:700'>{n}</div>"
                ),
            )
            folium.Marker(
                (s["y"], s["x"]), icon=icon, tooltip=f"{n}. {s['name']}",
                popup=folium.Popup(popup, max_width=260),
            ).add_to(m)
    if len(pts) > 1:
        m.fit_bounds(pts, padding=(30, 30))
    st_folium(
        m, height=460, use_container_width=True, returned_objects=[], key=f"map_{key}_{sel}"
    )
    st.caption(
        "마커 번호는 방문 순서, 색은 종류(식사·카페·실내·실외)예요. 마커를 누르면 상세 정보가 나와요. "
        "점선은 장소를 순서대로 이은 직선입니다. 지도: © OpenStreetMap"
    )


def render_cat_nav():
    """오른쪽에 고정된 카테고리 메뉴. 고른 카테고리는 이 채팅의 모든 일정 결과에 적용된다."""
    st.markdown(
        "<style>@media (min-width: 901px) { .block-container { padding-right: 9.5rem; } }</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="catnav"):
        st.radio("카테고리", CATEGORIES, key="cat", label_visibility="collapsed")


def render_trip_tabs(
    days: list[dict], weather: list[dict], note: str = "", key: str = "", packing=None
):
    """고정 메뉴(render_cat_nav)에서 고른 카테고리의 내용을 보여준다."""
    choice = st.session_state.get("cat", CAT_PLAN)
    if choice == CAT_PLAN:
        st.markdown(days_html(days), unsafe_allow_html=True)
        if packing:  # 일정과 함께 준비물도 한 번에 보여준다
            st.markdown("#### 🎒 이 일정에 맞는 준비물")
            st.markdown(packing_html(packing), unsafe_allow_html=True)
        st.caption(
            "이동시간: 자차는 카카오 길찾기 기준(실패 시 예상), 도보는 거리 기반 예상입니다."
            + (
                " 대중교통은 ODsay 길찾기 기준입니다."
                if config.ODSAY_API_KEY
                else " 대중교통(버스·지하철)은 .env에 ODSAY_API_KEY를 넣으면 표시됩니다."
            )
        )
    elif choice == CAT_MAP:
        map_view(days, key)
    elif choice == CAT_WEATHER:
        if weather:
            st.markdown(weather_html(weather), unsafe_allow_html=True)
            st.caption("날씨 제공: Open-Meteo (날마다 그날 방문하는 장소 위치 기준)")
        else:
            st.info(note or "날씨 정보를 가져오지 못했어요.")
    elif choice == CAT_PACK:
        if packing:
            st.markdown(packing_html(packing), unsafe_allow_html=True)
        else:
            st.info("이 일정에는 준비물 정보가 없어요. 새로 일정을 만들면 함께 나와요.")
    else:
        kind = CATEGORY_KIND[choice]
        seen, items = set(), []
        for d in days:
            for s in d["stops"]:
                if s["kind"] == kind and s["name"] not in seen:
                    seen.add(s["name"])
                    items.append({**s, "reason": s["note"], "blogs": []})
        if items:
            st.markdown(cards_html(items), unsafe_allow_html=True)
        else:
            st.info(f"이 일정에는 '{kind}' 장소가 없어요.")


def plain(text: str) -> str:
    # ~ 는 취소선, $ 는 수식으로 해석되므로 글자 그대로 보이게 이스케이프한다
    return text.replace("~", "\\~").replace("$", "\\$")


def render_body(m: dict, key: str = "live"):
    st.markdown(plain(m["content"]))
    if m.get("days"):
        render_trip_tabs(
            m["days"], m.get("weather", []), m.get("weather_note", ""), key, m.get("packing")
        )
    if m.get("places"):
        st.markdown(cards_html(m["places"]), unsafe_allow_html=True)


def render(m: dict, key: str):
    with st.chat_message(m["role"]):
        render_body(m, key)


def to_langchain_messages(history, system=config.SYSTEM_PROMPT):
    msgs = [SystemMessage(content=system)]
    for m in history:
        cls = HumanMessage if m["role"] == "user" else AIMessage
        msgs.append(cls(content=m.get("llm_text", m["content"])))
    return msgs


def valid_dates(plan: Plan) -> tuple[str, str]:
    """계획의 여행 날짜가 올바른 형식이면 (시작, 종료), 아니면 ('', '')."""
    try:
        s = datetime.strptime(plan.start_date, "%Y-%m-%d")
        e = datetime.strptime(plan.end_date or plan.start_date, "%Y-%m-%d")
    except ValueError:
        return "", ""
    if e < s or (e - s).days > 14:
        return "", ""
    return s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")


def gather_candidates(
    llm, history, force_itinerary=False, areas=None
) -> tuple[dict, Plan]:
    """대화에서 검색어를 정하고 카카오에서 실제 장소를 모은다. ({이름: 장소}, 계획)"""
    today = datetime.now().strftime("%Y-%m-%d")
    plan = llm.with_structured_output(Plan).invoke(
        to_langchain_messages(history, f"오늘 날짜: {today}\n" + config.PLANNER_PROMPT)
    )
    if force_itinerary:
        plan.itinerary = True
    if areas:
        plan.areas = areas
    queries = list(plan.queries[:6])
    if plan.itinerary:
        # 식사·카페·실내·실외 후보를 코드에서 항상 확보한다
        # 카카오 키워드 검색은 단어를 여러 개 붙이면 결과가 비므로 한 단어씩 검색한다
        for area in plan.areas[:3]:
            queries += [f"{area} {kind}" for kind in ("맛집", "카페", "박물관", "미술관", "공원", "해수욕장")]
    found: dict[str, dict] = {}
    for q in dict.fromkeys(queries):  # 중복 검색어 제거
        for p in kakao.search(q, size=3):
            found.setdefault(p["name"], p)
    return found, plan


@traceable(name="travel_reply", run_type="chain", tags=["travel-chatbot"])
def build_reply(history, dates=None, force_itinerary=False, areas=None) -> dict:
    """대화(history)로 답변을 만든다. 장소·이동시간·날씨까지 채운 메시지 dict를 돌려준다."""
    llm = ChatOpenAI(model=config.OPENAI_MODEL, api_key=config.OPENAI_API_KEY)
    candidates, plan = (
        gather_candidates(llm, history, force_itinerary, areas)
        if kakao.has_key()
        else ({}, Plan())
    )
    weather = []
    w_start, w_end = dates or valid_dates(plan)
    weather_note = ""
    system = config.SYSTEM_PROMPT
    if candidates:
        lines = "\n".join(
            f"- {p['name']} | {p['category']} | {p['address']}"
            for p in candidates.values()
        )
        system += "\n\n" + config.GROUNDED_PROMPT + "\n\n후보 장소:\n" + lines
        pts = [p for p in candidates.values() if p["x"] and p["y"]]
        if pts:
            weather = trip.forecast(
                sum(p["y"] for p in pts) / len(pts),
                sum(p["x"] for p in pts) / len(pts),
                w_start,
                w_end,
            )
        if w_start and not weather:
            weather_note = (
                f"{w_start} ~ {w_end} 예보는 아직 제공되지 않아요 "
                "(오늘부터 약 16일 앞까지만 조회됩니다)."
            )
            system += "\n\n날씨 예보: 여행 날짜의 예보는 아직 없음. 날씨를 지어내지 마."
        if weather:
            system += "\n\n날씨 예보:\n" + "\n".join(
                f"- {w['date']} {w['text']} {w['tmin']:.0f}~{w['tmax']:.0f}도 "
                f"강수확률 {w['rain']}%"
                for w in weather
            )
    if plan.weather_places and kakao.has_key():
        # 날씨를 묻는 질문: 장소 후보와 상관없이 묻는 지역·날짜로 따로 조회한다
        blocks = []
        for name in plan.weather_places[:3]:
            hit = kakao.search(name, size=1)
            got = (
                trip.forecast(hit[0]["y"], hit[0]["x"], w_start, w_end)
                if hit and hit[0]["x"]
                else []
            )
            if got:
                blocks.append(
                    f"[{name}]\n"
                    + "\n".join(
                        f"- {w['date']} {w['text']} {w['tmin']:.0f}~{w['tmax']:.0f}도 "
                        f"강수확률 {w['rain']}%"
                        for w in got
                    )
                )
        if blocks:
            system += (
                "\n\n지역별 날씨 예보(Open-Meteo, 이 데이터로 날씨 질문에 답해. "
                "'확인할 수 없다'고 하지 마):\n" + "\n".join(blocks)
            )
        else:
            system += (
                "\n\n요청한 날짜·지역의 날씨 예보를 가져오지 못했어. "
                "예보는 오늘부터 약 16일 앞까지만 조회돼. 날씨를 지어내지 말고 그렇게 안내해."
            )
    reply = llm.with_structured_output(TravelReply).invoke(
        to_langchain_messages(history, system)
    )
    places = []
    for pick in reply.picks:
        p = candidates.get(pick.name)  # 후보에 없는 이름은 버린다
        if p and all(x["name"] != p["name"] for x in places):
            places.append(
                {
                    **p,
                    "reason": pick.reason,
                    "blogs": naver.search_blogs(
                        f"{p['address'].split(' ')[0]} {p['name']}"
                    )
                    if p["is_food"]
                    else [],
                }
            )
    days = []
    for day in reply.days:
        stops = [
            {**candidates[s.name], "time": s.time, "kind": s.kind, "note": s.note}
            for s in day.stops
            if s.name in candidates  # 후보에 없는 장소는 버린다
        ]
        for prev, cur in zip(stops, stops[1:]):
            if prev["x"] and cur["x"]:
                cur["leg"] = trip.leg(prev, cur)
        if stops:
            days.append({"title": day.title, "stops": stops})
    first = datetime.strptime(w_start, "%Y-%m-%d") if w_start else datetime.now()
    for i, d in enumerate(days):
        # 일차·날짜를 코드에서 직접 붙인다 (날짜는 여행 날짜를 알 때만)
        d["label"] = f"{i + 1}일차"
        if w_start:
            dt = first + timedelta(days=i)
            d["date"] = f"{dt.month}/{dt.day}({'월화수목금토일'[dt.weekday()]})"
    if days and kakao.has_key():
        # 날마다 그날 방문 장소들의 위치·날짜로 날씨를 따로 조회한다
        per_day = []
        for i, d in enumerate(days):
            pts = [s for s in d["stops"] if s["x"] and s["y"]]
            if not pts:
                continue
            date = (first + timedelta(days=i)).strftime("%Y-%m-%d")
            got = trip.forecast(
                sum(s["y"] for s in pts) / len(pts),
                sum(s["x"] for s in pts) / len(pts),
                date,
                date,
            )
            if got:
                got[0]["place"] = " ".join(pts[0]["address"].split()[:2])
                got[0]["label"] = day_name(d)
                per_day.append(got[0])
        if per_day:
            weather = per_day
    # 이후 대화에서 챗봇이 확정된 일정을 기억하도록 시간표를 텍스트로도 남긴다
    llm_text = reply.answer
    if days:
        llm_text += "\n\n[확정된 일정]\n" + "\n".join(
            f"{day_name(d)} {d.get('date', '')}: "
            + " → ".join(f"{s['time']} {s['name']}({s['kind']})" for s in d["stops"])
            for d in days
        )
    return {
        "role": "assistant",
        "content": reply.answer,
        "llm_text": llm_text,
        "places": [] if days else places,
        "days": days,
        "packing": [g.model_dump() for g in reply.packing] if days else [],
        "weather": weather if days else [],
        "weather_note": weather_note,
    }


def show_error(e: Exception):
    if isinstance(e, kakao.KakaoError):
        st.error(
            f"카카오 장소 검색에 실패했습니다. ({e}) "
            "키 값과, 카카오 개발자 콘솔에서 앱의 '카카오맵' 사용 설정을 확인해 주세요."
        )
    else:
        # 오류 메시지에 키가 섞일 수 있으므로 종류만 보여준다.
        st.error(
            f"답변을 가져오지 못했습니다. (오류 종류: {type(e).__name__}) "
            "키와 모델 이름 설정을 확인해 주세요."
        )


def ask(question: str):
    with st.chat_message("user"):
        st.markdown(plain(question))
    try:
        with st.chat_message("assistant"):
            with st.spinner("실제 장소를 찾고 답변을 만드는 중..."):
                history = st.session_state.messages + [{"role": "user", "content": question}]
                msg = build_reply(
                    history,
                    langsmith_extra={"metadata": {"mode": "chat", "chat_id": st.session_state.cid}},
                )
            render_body(msg)
            if not kakao.has_key():
                st.caption("⚠️ KAKAO_REST_API_KEY가 없어 실제 장소 검색 없이 답했습니다.")
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.messages.append(msg)
        chat = st.session_state.chats[st.session_state.cid]
        if chat["title"] == "새 채팅":
            chat["title"] = question[:18]
        save_chats()
        st.rerun()  # 사이드바 제목을 바로 갱신
    except Exception as e:
        show_error(e)


def planner_page():
    st.subheader("🗓 상세 일정 짜기")
    st.caption("여행지와 날짜를 정하면 카카오맵의 실제 장소로 날짜별 시간표를 만들어요.")
    with st.form("plan_form"):
        dest = st.text_input("여행지", placeholder="예: 부산, 제주 서귀포, 강릉")
        c1, c2 = st.columns(2)
        today = date.today()
        start = c1.date_input("시작일", today + timedelta(days=3))
        end = c2.date_input("종료일", today + timedelta(days=4))
        c3, c4 = st.columns(2)
        people = c3.number_input("인원", min_value=1, max_value=20, value=2)
        move = c4.selectbox("주 이동수단", ["자차", "도보·대중교통"])
        styles = st.multiselect(
            "여행 스타일",
            ["맛집", "카페", "자연·풍경", "문화·역사", "쇼핑", "휴식·힐링", "체험·액티비티"],
            default=["맛집", "카페"],
        )
        extra = st.text_area("추가 요청 (선택)", height=80, placeholder="예: 아이와 함께, 비 오면 실내 위주")
        go = st.form_submit_button("🗓 일정 만들기", use_container_width=True)

    if go:
        n_days = (end - start).days + 1
        if not dest.strip():
            st.warning("여행지를 입력해 주세요.")
        elif end < start:
            st.error("종료일이 시작일보다 빠릅니다.")
        elif n_days > 7:
            st.error("일정은 최대 7일까지 만들 수 있어요.")
        elif not config.OPENAI_API_KEY:
            st.error(".env 파일에 OPENAI_API_KEY가 설정되어 있지 않습니다.")
        elif not kakao.has_key():
            st.error(".env 파일에 KAKAO_REST_API_KEY가 필요합니다. 실제 장소 검색에 쓰여요.")
        else:
            question = (
                f"{dest.strip()} {start:%m/%d}~{end:%m/%d} ({n_days}일) 상세 일정 짜줘. "
                f"인원 {people}명, 주 이동수단 {move}"
                + (f", 선호 스타일: {', '.join(styles)}" if styles else "")
                + (f". 추가 요청: {extra.strip()}" if extra.strip() else "")
                + f". days는 정확히 {n_days}개(날짜별)로, 하루 4~6곳을 식사·카페·실내·실외가 "
                "균형 잡히게 넣고, 하루 동선은 가까운 동네끼리 묶어 줘."
            )
            try:
                with st.spinner("실제 장소를 찾고 날짜별 일정을 만드는 중... (30초 안팎)"):
                    msg = build_reply(
                        [{"role": "user", "content": question}],
                        dates=(start.isoformat(), end.isoformat()),
                        force_itinerary=True,
                        langsmith_extra={"metadata": {"mode": "planner", "dest": dest.strip()}},
                    )
                cid = datetime.now().strftime("%Y%m%d%H%M%S%f")
                st.session_state.chats[cid] = {
                    "title": f"🗓 {dest.strip()} {start:%m/%d}~{end:%m/%d}",
                    "messages": [{"role": "user", "content": question}, msg],
                }
                switch_chat(cid, goto_chat=False)
                save_chats()
                st.session_state.plan_result = msg
                st.rerun()  # 사이드바 여행 기록을 바로 갱신
            except Exception as e:
                show_error(e)

    result = st.session_state.get("plan_result")
    if result:
        render_cat_nav()
        st.success("일정이 '여행 기록'에 저장됐어요. 💬 질문하기에서 이어서 고칠 수 있어요.")
        render_body(result, "plan")


if st.session_state.mode is None:
    st.markdown(
        '<div class="home-hero"><h1>🧳 여행챗봇</h1>'
        "<p>카카오맵의 실제 장소로 여행 일정과 맛집을 추천해 드려요</p></div>",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            '<div class="mode-card"><div class="mc-icon">💬</div>'
            '<div class="mc-title">질문하기</div>'
            '<div class="mc-desc">어디로 여행 갈지 모를 때<br>'
            "여행 꿀팁 등 자유롭게 질문하고 싶을 때</div></div>",
            unsafe_allow_html=True,
        )
        st.button(
            "질문하기 시작", key="home_chat", on_click=new_chat,  # 새 채팅을 만들고 시작
            type="primary", use_container_width=True,
        )
    with c2:
        st.markdown(
            '<div class="mode-card"><div class="mc-icon">🗓</div>'
            '<div class="mc-title">일정 짜기</div>'
            '<div class="mc-desc">여행 일정과 지역이 정해졌을 때<br>'
            "날짜별 상세 일정을 받고 싶을 때</div></div>",
            unsafe_allow_html=True,
        )
        st.button(
            "일정 짜기 시작", key="home_plan", on_click=set_mode, args=(PLAN_MODE,),
            type="primary", use_container_width=True,
        )
    st.stop()

st.markdown(
    '<div class="hero"><h1>🧳 여행 챗봇</h1>'
    "<p>카카오맵의 실제 장소로 일정과 맛집을 추천해요. 이전 대화를 기억해요.</p></div>",
    unsafe_allow_html=True,
)

if st.session_state.mode == PLAN_MODE:
    planner_page()
    st.stop()

if any(m.get("days") for m in st.session_state.messages):
    render_cat_nav()

st.markdown('<div id="first-question"></div>', unsafe_allow_html=True)
for i, m in enumerate(st.session_state.messages):
    render(m, f"{st.session_state.cid}_{i}")

typed = st.chat_input("여행에 대해 질문해 보세요")
from_button = typed is None and st.session_state.pending is not None
question = typed if typed is not None else st.session_state.pending
st.session_state.pending = None

if question is not None:
    if from_button and not st.session_state.messages:
        st.info("먼저 가고 싶은 여행지를 입력해 주세요. 예: 부산 2박 3일 여행 갈 거야")
    elif not question.strip():
        st.warning("질문을 입력해 주세요.")
    elif not config.OPENAI_API_KEY:
        st.error(".env 파일에 OPENAI_API_KEY가 설정되어 있지 않습니다.")
    else:
        ask(question.strip())

CTX = "지금까지 우리가 이야기한 그 여행지(여행 기간·인원·취향도 반영해서) 기준으로 "
QUICK = {
    "🍜 맛집 추천": CTX + "맛집을 추천해줘",
    "🗺️ 코스 짜기": CTX + "여행 코스를 짜줘",
    "🚆 교통": CTX + "교통수단과 이동 방법을 알려줘",
    "🎒 준비물": CTX + "준비물 체크리스트를 알려줘",
}


def set_pending(text):
    st.session_state.pending = text


cols = st.columns(len(QUICK) + 1)
for col, (label, text) in zip(cols, QUICK.items()):
    col.button(label, on_click=set_pending, args=(text,), use_container_width=True)
cols[-1].button(
    "📍 첫 질문으로", on_click=lambda: st.session_state.update(scroll_first=True),
    use_container_width=True,
)

if st.session_state.pop("scroll_first", False):
    # 이 채팅에서 처음 물어본 질문 위치로 부드럽게 스크롤한다
    # 화면이 다시 그려진 뒤 자동 스크롤에 덮이지 않도록 여러 번 시도한다
    # (같은 내용이면 iframe이 다시 실행되지 않아서 매번 번호를 바꿔 넣는다)
    st.session_state.scroll_n = st.session_state.get("scroll_n", 0) + 1
    components.html(
        f"<script>// {st.session_state.scroll_n}\n"
        "const go = () => { const m = window.parent.document.querySelector("
        "'[data-testid=\"stChatMessage\"]'); if (m) m.scrollIntoView({block: 'center'}); };"
        "let tries = 0; const t = setInterval(() => { go(); if (++tries > 15) clearInterval(t); }, 200);"
        "</script>",
        height=0,
    )
