import os

import uvicorn


def run_api() -> None:
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("theminjoo_api_mcp.api:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    run_api()
