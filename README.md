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
- **ChatGPT Plus용 브라우저 UI: `/app` 또는 `/plus`**
- **AI 읽기용 Markdown 피드: `/v1/markdown`**
- 원격 MCP(Streamable HTTP): `/mcp`
- 로컬 MCP(stdio): `theminjoo-mcp`
- MCP tools: `list_posts`, `get_post`, `search_posts`
- OAuth 2.1 호환 Authorization Code + PKCE(S256)
- MCP Protected Resource Metadata + Authorization Server Metadata
- Dynamic Client Registration(DCR)
- `offline_access` + refresh token
- OAuth access token의 MCP resource binding
- 선택적 legacy static Bearer token
- 5분 기본 TTL 캐시
- pytest, Ruff, Docker, GitHub Actions CI
- Railway / Render 배포 지원

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
GET /v1/markdown?board=11&limit=30
GET /v1/markdown/{board}/{post_id}
GET /app
GET /plus
```

## ChatGPT Plus에서 사용

개인용 ChatGPT Plus에서는 커스텀 MCP를 직접 설치할 수 없으므로, 같은 데이터를 **일반 웹 URL과 Markdown 피드**로 사용할 수 있습니다.

### 웹 화면

```text
https://theminjoo-api-mcp-production.up.railway.app/app
```

또는:

```text
https://theminjoo-api-mcp-production.up.railway.app/plus
```

웹 화면에서는:

- 논평·브리핑 / 모두발언 전환
- 최신 글 보기
- 제목 검색
- 본문 보기
- 공식 원문 열기
- AI용 Markdown 본문 열기
- ChatGPT에 붙여넣을 질문 문구 복사

를 할 수 있습니다.

### ChatGPT가 읽기 쉬운 공개 URL

최신 논평·브리핑:

```text
https://theminjoo-api-mcp-production.up.railway.app/v1/markdown?board=11&limit=30
```

최신 모두발언:

```text
https://theminjoo-api-mcp-production.up.railway.app/v1/markdown?board=230&limit=30
```

ChatGPT Plus 대화에서 위 URL을 붙여넣고 다음처럼 요청할 수 있습니다.

```text
이 공개 URL을 읽고 최신 논평·브리핑을 핵심 내용, 인물, 날짜, 원문 링크 중심으로 요약해줘:
https://theminjoo-api-mcp-production.up.railway.app/v1/markdown?board=11&limit=30
```

이 방식은 MCP 연결이 아니라 일반 HTTPS 공개 페이지를 읽는 방식입니다.

## 원격 MCP

원격 MCP는 같은 FastAPI 프로세스의 `/mcp`에 Streamable HTTP로 마운트됩니다.

### MCP tools

- `list_posts(board, offset=0, limit=20)`
- `get_post(board, post_id)`
- `search_posts(board, query, pages=3)`

`board` 값:

- `11`: 논평·브리핑
- `230`: 모두발언

## OAuth 2.1 / MCP Authorization

원격 `/mcp`는 기본적으로 OAuth Bearer access token을 요구합니다. 인증 없이 접근하면 HTTP 401과 함께 `WWW-Authenticate`의 `resource_metadata` 위치를 반환합니다.

### Discovery / OAuth 엔드포인트

```text
GET  /.well-known/oauth-protected-resource
GET  /.well-known/oauth-protected-resource/mcp
GET  /.well-known/oauth-authorization-server
GET  /.well-known/openid-configuration

POST /register
GET  /authorize
POST /authorize
POST /token

# 이전 버전 호환 aliases
POST /oauth/register
GET  /oauth/authorize
POST /oauth/authorize
POST /oauth/token
```

지원 기능:

- Authorization Code
- PKCE `S256`
- Dynamic Client Registration(DCR)
- public client (`token_endpoint_auth_method=none`)
- `application_type=web|native`
- RFC 9207 `iss` authorization response parameter
- RFC 8707 스타일 `resource` binding
- `offline_access` + refresh token
- Bearer access token

## Claude 연결

Claude의 Custom Connector에 아래 URL을 등록합니다.

```text
https://theminjoo-api-mcp-production.up.railway.app/mcp
```

정상 흐름:

1. Claude가 `/mcp`에 접근하고 401 + Protected Resource Metadata를 확인
2. Authorization Server Metadata를 조회
3. DCR로 OAuth public client를 자동 등록
4. 브라우저에서 승인 화면 표시
5. **연결 허용**
6. PKCE code exchange 후 MCP 연결

이 서버는 자동 DCR을 지원하므로 임의의 고정 Client ID를 수동 입력할 필요가 없습니다. 이전 연결 시도의 메타데이터가 캐시된 상태에서 “OAuth 클라이언트 ID를 수동으로 추가” 메시지가 계속 보이면 기존 커넥터를 삭제하고 새로 추가하세요.

## ChatGPT 연결

지원되는 ChatGPT Developer Mode / Custom MCP App 환경에서도 같은 MCP URL을 사용합니다.

```text
https://theminjoo-api-mcp-production.up.railway.app/mcp
```

OAuth 연결에서는 `offline_access`를 discovery metadata에 광고하고 refresh token을 발급합니다.

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
docker run --rm -p 8000:8000 \
  -e THEMINJOO_OAUTH_SECRET='replace-with-a-long-random-secret' \
  theminjoo-api-mcp
```

공개 배포에서는 `THEMINJOO_PUBLIC_URL`도 설정하세요.

```text
THEMINJOO_PUBLIC_URL=https://your-service.example.com
```

## Legacy static Bearer token

OAuth 외에 운영자가 직접 발급한 고정 Bearer token을 병행하려면:

```text
THEMINJOO_MCP_TOKEN=your-static-token
```

이 값은 선택 사항입니다. Claude/ChatGPT OAuth 연결에는 필요하지 않습니다.

## 환경변수

`.env.example` 참고:

```text
THEMINJOO_BASE_URL=https://theminjoo.kr/main/sub/news
THEMINJOO_REQUEST_TIMEOUT=15
THEMINJOO_CACHE_TTL_SECONDS=300
THEMINJOO_DEFAULT_PAGE_SIZE=20
THEMINJOO_MAX_PAGE_SIZE=100
THEMINJOO_PUBLIC_URL=https://your-service.example.com
THEMINJOO_OAUTH_SECRET=replace-with-a-long-random-secret
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

테스트는 다음을 포함합니다.

- REST health / boards
- OAuth discovery metadata
- MCP 401 challenge
- RFC 7591 형태 DCR 응답
- PKCE 승인
- authorization code → access/refresh token
- OAuth Bearer access token으로 실제 MCP `initialize`

## 프로젝트 구조

```text
src/theminjoo_api_mcp/
  api.py
  client.py
  parser.py
  mcp_server.py
  oauth.py
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
