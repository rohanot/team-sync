import os
import uvicorn

from app.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.api_port))
    uvicorn.run("app.main:app", host=settings.api_host, port=port, reload=settings.app_env == "development")

