import uvicorn


def run_api() -> None:
    uvicorn.run("theminjoo_api_mcp.api:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_api()
