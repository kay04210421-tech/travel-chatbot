import os

from dotenv import load_dotenv

load_dotenv()

# 모델명은 .env의 OPENAI_MODEL로 바꾼다. 비어 있으면 아래 기본값을 쓴다.
DEFAULT_MODEL = "gpt-4o-mini"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()

# LangSmith 추적: .env에 LANGSMITH_TRACING=true 와 LANGSMITH_API_KEY 를 넣으면 켜진다.
# LangChain/langsmith가 이 환경변수를 직접 읽으므로, 여기서는 프로젝트 이름 기본값과 켜짐 여부만 다룬다.
os.environ.setdefault("LANGSMITH_PROJECT", "travel-chatbot")
LANGSMITH_ON = (
    os.getenv("LANGSMITH_TRACING", "").strip().lower() in ("true", "1")
    and bool(os.getenv("LANGSMITH_API_KEY", "").strip())
)
LANGSMITH_PROJECT = os.environ["LANGSMITH_PROJECT"]

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "").strip()
# 대중교통(버스 번호·지하철 노선) 길찾기. 없으면 대중교통 정보는 표시하지 않는다.
ODSAY_API_KEY = os.getenv("ODSAY_API_KEY", "").strip()

SYSTEM_PROMPT = (
    "너는 친절한 여행 도우미야. 여행지, 일정, 교통, 음식, 준비물에 대해 "
    "한국어로 간결하고 실용적으로 답해줘. 별점이나 리뷰 내용은 지어내지 마."
)

PLANNER_PROMPT = (
    "대화를 보고 사용자의 마지막 요청에 답하려면 어떤 실제 장소를 검색해야 하는지 정해줘. "
    "검색어는 '지역 + 종류 한 단어' 형태로 최대 6개(예: '강릉 맛집', '강릉 카페'). "
    "단어를 여러 개 붙이면 결과가 안 나오니 종류는 한 단어만 써. "
    "사용자가 여행 날짜를 말했으면 start_date/end_date에 YYYY-MM-DD로 넣어(연도가 없으면 "
    "오늘 이후 가장 가까운 날짜). 말하지 않았으면 빈 문자열로 둬. "
    "날씨·기온·비 오는지를 묻는 질문이면 weather_places에 날씨를 알고 싶은 지역 이름을 넣어 "
    "(대화에 나온 지역·날짜 기준). 이때 날짜를 말하지 않았으면 오늘부터 며칠로 본다. "
    "일정·코스 요청이면 itinerary를 true로 하고 areas에 방문할 동네(하루 하나, 최대 3개)를 넣어. "
    "당일치기나 하루 일정이면 도시 전체가 아니라 한 구·동네(예: 해운대, 광안리)로 좁혀서 "
    "'해운대 맛집'처럼 검색어를 만들어 이동이 짧게 해. 며칠 일정이면 날마다 동네를 달리해도 돼. "
    "준비물·교통 등 장소가 필요 없으면 빈 목록."
)

GROUNDED_PROMPT = (
    "아래 '후보 장소'는 카카오맵에서 검색한 실제 장소야. "
    "장소를 추천하거나 일정을 짤 때는 반드시 이 후보 안에서만 골라 이름을 정확히 그대로 써. "
    "후보에 없는 가게나 관광지 이름을 만들어 내지 마. 후보가 부족하면 솔직히 말해. "
    "picks에는 답변에서 언급한 후보 이름과 한 줄 이유를 담아.\n"
    "사용자가 일정·코스를 짜 달라고 하면 days에 날짜별 stops(시간 순)를 채워. "
    "각 stop의 kind는 식사/카페/실내/실외 중 하나: 식당=식사, 카페·디저트=카페, "
    "박물관·전시·쇼핑 등 지붕 있는 곳=실내, 해변·공원·산책로 등 야외=실외. "
    "같은 날 stops는 주소가 가까운 동네끼리 묶어서 이동이 짧게 하고(걸어서 20분 안팎이 이상적), "
    "사용자가 말한 종류(식사·카페·실내·실외)는 후보에 있으면 빠짐없이 포함하고, "
    "점심·저녁 식사와 카페, 실내·실외 장소를 균형 있게 넣고, 날씨 정보가 있으면 비·눈 오는 날은 실내를, "
    "맑은 날은 실외를 더 넣어. answer에는 일정 요약과 날씨 팁만 짧게 쓰고 "
    "장소별 시간표는 days에만 넣어. days의 title에는 날짜나 'N일차' 없이 그날의 동네만 써. "
    "일정을 짤 때는 packing에도 날씨 예보와 일정(실내·실외 비율, 걷는 양, 계절)에 맞춘 준비물을 "
    "분류별(필수품·의류·날씨 대비·전자기기·기타)로 한 번에 담아. "
    "일정 요청이 아니면 days와 packing은 빈 목록."
)
