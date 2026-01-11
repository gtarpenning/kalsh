"""Start the FastAPI backend server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "kalsh.api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
