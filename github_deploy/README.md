# 🧳 여행챗봇

카카오맵의 **실제 장소**를 기반으로 여행 일정과 맛집을 추천하는 챗봇입니다. (Python · Streamlit · LangChain · OpenAI)

## 기능

- **질문하기** — 어디로 갈지 모를 때, 여행 꿀팁 등 자유롭게 질문 (이전 대화를 기억)
- **일정 짜기** — 여행지·날짜를 정하면 날짜별 상세 일정 생성
  - 일차·날짜 구분, 식사/카페/실내/실외 분류
  - 장소 사이 도보·자차(·대중교통) 이동시간
  - 날짜별 날씨 예보, 방문 순서 지도, 일정에 맞춘 준비물
- 가게 이름을 누르면 네이버 지도(별점·리뷰)로 연결, 네이버 블로그 후기 미리보기(선택)
- 여행 기록을 왼쪽에 저장하고 새 채팅으로 다른 여행지를 따로 상담
- LangSmith로 호출 과정 추적(선택)

장소는 카카오 로컬 API 검색 결과 안에서만 고르므로, 존재하지 않는 가게를 만들어 내지 않습니다.

## 실행 방법

Python 3.12 기준입니다.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# .env 를 열어 키를 채운 뒤
streamlit run app.py
```

브라우저에서 http://localhost:8501 로 접속합니다.

## 환경 변수 (`.env`)

| 변수 | 필수 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 |
| `OPENAI_MODEL` | | 사용할 모델 이름 (비우면 기본값) |
| `KAKAO_REST_API_KEY` | ✅ | 카카오 개발자 REST API 키 (카카오맵 사용 설정 필요) |
| `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` | | 네이버 검색 API, 블로그 후기 미리보기 |
| `ODSAY_API_KEY` | | ODsay 대중교통 길찾기 (버스 번호·지하철 노선 표시) |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | | LangSmith 추적 (`LANGSMITH_TRACING=true`로 켬) |

> ⚠️ `.env` 파일은 절대 GitHub에 올리지 마세요. `.gitignore`에 제외되어 있습니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `app.py` | Streamlit 화면과 일정 생성 흐름 |
| `config.py` | 환경변수·프롬프트 설정 |
| `kakao.py` | 카카오 장소 검색 |
| `naver.py` | 네이버 지도 링크, 블로그 검색 |
| `trip.py` | 이동시간(카카오 길찾기·ODsay), 날씨(Open-Meteo) |

## 참고

- 날씨는 [Open-Meteo](https://open-meteo.com/)(키 불필요)를 사용하며, 오늘부터 약 16일 앞까지만 조회됩니다.
- 도보 이동시간은 직선거리 기반 예상값입니다.
- 대화 기록은 로컬 `chats.json`에 저장되며 저장소에는 포함되지 않습니다.
