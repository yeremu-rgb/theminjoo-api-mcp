# theminjoo-api-mcp

더불어민주당 공식 홈페이지의 공개 게시물 중 **논평·브리핑(`brd=11`)**과 **모두발언(`brd=230`)**을 읽어 REST API와 MCP(Model Context Protocol)로 제공하는 비공식 오픈소스 프로젝트입니다.

> 이 프로젝트는 더불어민주당의 공식 프로젝트가 아닙니다. 원문 저작권과 이용 조건은 원 출처에 따르며, 운영 시 원 사이트에 과도한 요청을 보내지 않도록 캐시와 적절한 호출 간격을 사용하세요.

## 원본 데이터

- 논평·브리핑: https://theminjoo.kr/main/sub/news/list.php?brd=11
- 모두발언: https://theminjoo.kr/main/sub/news/list.php?brd=230

## 기능

- `brd=11`: 논평·브리핑 목록/본문
- `brd=230`: 모두발언 목록/본문
- FastAPI REST API + OpenAPI
- **원격 MCP(Streamable HTTP): `/mcp`**
- 로컬 MCP(stdio): `theminjoo-mcp`
- MCP tools: `list_posts`, `get_post`, `search_posts`
- 선택적 Bearer Token 인증
- CORS/MCP 헤더 지원
- 5분 기본 TTL 캐시
- pytest, Ruff, Docker, GitHub Actions CI
- Render 배포 Blueprint

## 설치

```bash
git clone https://github.com/yeremu-rgb/theminjoo-api-mcp.git
cd theminjoo-api-mcp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

## REST API + 원격 MCP 실행

```bash
theminjoo-api
```

기본 주소:

- REST: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- MCP Streamable HTTP: `http://localhost:8000/mcp`
- Health check: `http://localhost:8000/health`

배포 플랫폼에서 `PORT` 환경변수를 제공하면 자동으로 해당 포트를 사용합니다.

### REST 엔드포인트

```text
GET /health
GET /v1/boards
GET /v1/posts?board=11&offset=0&limit=20
GET /v1/posts?board=230&offset=0&limit=20
GET /v1/posts/{board}/{post_id}
GET /v1/search?board=11&q=키워드&pages=3
```

## 원격 MCP

원격 MCP는 같은 FastAPI 프로세스의 `/mcp`에 **Streamable HTTP**로 마운트됩니다.

### MCP tools

- `list_posts(board, offset=0, limit=20)`
- `get_post(board, post_id)`
- `search_posts(board, query, pages=3)`

`board` 값:

- `11`: 논평·브리핑
- `230`: 모두발언

### Bearer Token 보호

공개 인터넷에 배포할 때 토큰 인증을 켜려면:

```bash
export THEMINJOO_MCP_TOKEN='change-me-to-a-long-random-secret'
theminjoo-api
```

MCP 요청에는 다음 헤더를 보냅니다.

```text
Authorization: Bearer change-me-to-a-long-random-secret
```

토큰을 설정하지 않으면 `/mcp`는 인증 없이 접근할 수 있습니다. REST API는 이 토큰과 무관하게 공개됩니다.

## 로컬 stdio MCP

```bash
theminjoo-mcp
```

stdio MCP 클라이언트 예시:

```json
{
  "mcpServers": {
    "theminjoo": {
      "command": "theminjoo-mcp"
    }
  }
}
```

## Docker

```bash
docker build -t theminjoo-api-mcp .
docker run --rm -p 8000:8000 theminjoo-api-mcp
```

토큰을 적용하려면:

```bash
docker run --rm -p 8000:8000 \
  -e THEMINJOO_MCP_TOKEN='change-me' \
  theminjoo-api-mcp
```

또는:

```bash
docker compose up --build
```

## Render 배포

저장소 루트의 `render.yaml`을 사용해 Render Blueprint로 배포할 수 있습니다.

1. Render에서 **New → Blueprint**
2. GitHub 저장소 `yeremu-rgb/theminjoo-api-mcp` 선택
3. 배포
4. 배포 URL이 `https://YOUR-SERVICE.onrender.com`이라면 MCP URL은:
   `https://YOUR-SERVICE.onrender.com/mcp`
5. 필요한 경우 Render 환경변수에 `THEMINJOO_MCP_TOKEN` 추가

## ChatGPT에 연결할 때

ChatGPT는 로컬 stdio 서버가 아니라 인터넷에서 접근 가능한 **원격 MCP URL**이 필요합니다. 따라서 먼저 Render 등 HTTPS 호스팅에 배포한 다음 배포된 `/mcp` URL을 ChatGPT의 커스텀 MCP/App 설정에 등록합니다.

예시:

```text
https://YOUR-SERVICE.onrender.com/mcp
```

토큰 인증을 켠 경우 연결 설정에도 동일한 Bearer Token을 입력합니다.

## 환경변수

`.env.example` 참고:

```text
THEMINJOO_BASE_URL=https://theminjoo.kr/main/sub/news
THEMINJOO_REQUEST_TIMEOUT=15
THEMINJOO_CACHE_TTL_SECONDS=300
THEMINJOO_DEFAULT_PAGE_SIZE=20
THEMINJOO_MAX_PAGE_SIZE=100
THEMINJOO_MCP_TOKEN=
THEMINJOO_CORS_ORIGINS=*
```

## 테스트

```bash
pip install -e '.[dev]'
ruff check .
pytest -q
python -m build
```

fixture 기반 테스트는 외부 사이트 장애와 무관하게 파서/API 기본 동작을 검증합니다.

## 프로젝트 구조

```text
src/theminjoo_api_mcp/
  api.py           # REST + /mcp mount
  client.py
  parser.py
  mcp_server.py    # MCP tools + stdio/HTTP 공용 FastMCP
  models.py
  config.py
tests/
  fixtures/
.github/workflows/ci.yml
Dockerfile
render.yaml
.env.example
```

## License

MIT. 단, 수집 대상 원문 콘텐츠의 권리는 해당 원문 권리자에게 있습니다.
