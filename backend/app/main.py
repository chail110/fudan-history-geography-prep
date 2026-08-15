from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import engine, Base, ensure_sqlite_schema
from app.courses import router as courses_router
from app.recommendations import router as recommendations_router
from app.exam import router as exam_router


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response

# Create tables
Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()

app = FastAPI(title="Bloom Learning API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(courses_router)
app.include_router(recommendations_router)
app.include_router(exam_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static files if they exist (must be last — catch-all mount)
frontend_dist = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
if os.path.exists(frontend_dist):
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="frontend")
