# theminjoo-api-mcp

더불어민주당 공식 홈페이지의 공개 게시물 중 **논평·브리핑(`brd=11`)**과 **모두발언(`brd=230`)**을 읽어 REST API와 MCP(Model Context Protocol) 도구로 제공하는 비공식 오픈소스 프로젝트입니다.

> 이 프로젝트는 더불어민주당의 공식 프로젝트가 아닙니다. 원문 저작권과 이용 조건은 원 출처에 따르며, 서비스 운영 시 원 사이트에 과도한 요청을 보내지 않도록 캐시와 적절한 호출 간격을 사용하세요.

## 원본 데이터

- 논평·브리핑: https://theminjoo.kr/main/sub/news/list.php?brd=11
- 모두발언: https://theminjoo.kr/main/sub/news/list.php?brd=230

## 기능

- `brd=11`: 논평·브리핑 목록/본문
- `brd=230`: 모두발언 목록/본문
- FastAPI 기반 REST API + OpenAPI 문서
- MCP stdio 서버: `list_posts`, `get_post`, `search_posts`
- 5분 기본 TTL 캐시
- HTML 구조 변화에 대응하기 위한 링크 기반 파싱
- pytest fixture 테스트, Ruff, Docker, GitHub Actions CI

## 설치

```bash
git clone https://github.com/yeremu-rgb/theminjoo-api-mcp.git
cd theminjoo-api-mcp
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e '.[dev]'
```

## REST API 실행

```bash
theminjoo-api
```

기본 주소는 `http://localhost:8000`, Swagger UI는 `/docs`입니다.

### 엔드포인트

```text
GET /health
GET /v1/boards
GET /v1/posts?board=11&offset=0&limit=20
GET /v1/posts?board=230&offset=0&limit=20
GET /v1/posts/{board}/{post_id}
GET /v1/search?board=11&q=키워드&pages=3
```

## MCP 서버

```bash
theminjoo-mcp
```

MCP 클라이언트 설정 예시:

```json
{
  "mcpServers": {
    "theminjoo": {
      "command": "theminjoo-mcp"
    }
  }
}
```

### MCP tools

- `list_posts(board, offset=0, limit=20)`
- `get_post(board, post_id)`
- `search_posts(board, query, pages=3)`

`board` 값은 `11`(논평·브리핑), `230`(모두발언)만 허용합니다.

## Docker

```bash
docker build -t theminjoo-api-mcp .
docker run --rm -p 8000:8000 theminjoo-api-mcp
```

또는:

```bash
docker compose up --build
```

## 환경변수

```text
THEMINJOO_BASE_URL=https://theminjoo.kr/main/sub/news
THEMINJOO_REQUEST_TIMEOUT=15
THEMINJOO_CACHE_TTL_SECONDS=300
THEMINJOO_DEFAULT_PAGE_SIZE=20
THEMINJOO_MAX_PAGE_SIZE=100
```

## 테스트

```bash
pip install -e '.[dev]'
ruff check .
pytest -q
```

테스트는 외부 사이트에 의존하지 않도록 HTML fixture를 사용합니다.

## 프로젝트 구조

```text
src/theminjoo_api_mcp/
  api.py
  client.py
  parser.py
  mcp_server.py
  models.py
  config.py
tests/
  fixtures/
.github/workflows/ci.yml
Dockerfile
```

## License

MIT. 단, 수집 대상 원문 콘텐츠의 권리는 해당 원문 권리자에게 있습니다.
