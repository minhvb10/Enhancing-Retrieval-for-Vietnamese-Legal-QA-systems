import logging
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import (
    BASE_DIR,
    EAGER_LOAD,
    MAX_QUERY_CHARS,
    SOURCE_PREVIEW_CHARS,
)
from app.llm import OllamaError, generate_answer
from app.retriever import LegalRetriever, RetrieverNotReadyError


logger = logging.getLogger(__name__)
retriever = LegalRetriever()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if EAGER_LOAD:
        try:
            retriever.load()
        except Exception:
            logger.exception(
                "Retriever startup failed; the health endpoint will report details"
            )
    yield


app = FastAPI(
    title="Vietnamese Legal QA",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "app" / "static"),
    name="static",
)
templates = Jinja2Templates(directory=BASE_DIR / "app" / "templates")


class AskRequest(BaseModel):
    query: str = Field(..., max_length=MAX_QUERY_CHARS)


class SourceItem(BaseModel):
    paragraph_id: str
    section_id: str
    score: float
    text: str


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceItem]


class HealthResponse(BaseModel):
    status: str
    retriever_ready: bool
    detail: str | None = None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ready" if retriever.is_ready else "not_ready",
        retriever_ready=retriever.is_ready,
        detail=retriever.load_error,
    )


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest):
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Bạn chưa nhập câu hỏi.")

    if not retriever.is_ready:
        try:
            retriever.load()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Hệ thống truy xuất chưa sẵn sàng: {exc}",
            ) from exc

    try:
        contexts = retriever.retrieve(query)
    except RetrieverNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Retrieval failed")
        raise HTTPException(
            status_code=500,
            detail=f"Không thể truy xuất dữ liệu pháp luật: {exc}",
        ) from exc

    try:
        answer = generate_answer(query, contexts)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AskResponse(
        answer=answer,
        sources=[
            SourceItem(
                paragraph_id=context.paragraph_id,
                section_id=context.section_id,
                score=context.score,
                text=context.text[:SOURCE_PREVIEW_CHARS],
            )
            for context in contexts
        ],
    )
