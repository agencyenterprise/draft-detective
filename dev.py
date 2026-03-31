import uvicorn
from lib.config.logger import setup_logger

if __name__ == "__main__":
    setup_logger()

    uvicorn.run(
        "lib.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        log_config=None,
    )
