"""FastAPI application for tumor likelihood predictions."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .schemas import ConfidenceAssessment, MetaResponse, PredictRequest, PredictResponse, PredictionLevelResult
from .scoring import TumorLikelihoodModel


def create_app(
    data_dir: Path | None = None,
    model: TumorLikelihoodModel | None = None,
) -> FastAPI:
    """Application factory used by uvicorn and tests."""
    root_dir = Path(__file__).resolve().parents[1]
    resolved_data_dir = data_dir or (root_dir / "data")

    app = FastAPI(
        title="GENIE Tumor Likelihood Tool",
        version="0.1.0",
        summary="Bayesian tumor-type likelihood ranking from mutation/CNA evidence.",
    )

    app.mount("/static", StaticFiles(directory=root_dir / "static"), name="static")
    templates = Jinja2Templates(directory=str(root_dir / "templates"))

    app.state.model = model
    app.state.data_dir = resolved_data_dir

    def get_model() -> TumorLikelihoodModel:
        if app.state.model is None:
            try:
                app.state.model = TumorLikelihoodModel.from_data_dir(app.state.data_dir)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return app.state.model

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve main web interface."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"title": "GENIE Tumor Likelihood Tool"},
        )

    @app.get("/tutorial", response_class=HTMLResponse)
    async def tutorial(request: Request) -> HTMLResponse:
        """Serve tutorial / reference guide page."""
        return templates.TemplateResponse(
            request=request,
            name="tutorial.html",
            context={"title": "How to Read the Results"},
        )

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        """Health endpoint with readiness check."""
        try:
            loaded_model = get_model()
            return {
                "status": "ok",
                "ready": True,
                "model_version": loaded_model.model_version(),
            }
        except HTTPException:
            return {
                "status": "degraded",
                "ready": False,
                "model_version": "unavailable",
            }

    @app.get("/api/v1/meta", response_model=MetaResponse)
    async def meta() -> MetaResponse:
        """Return model metadata and supported options."""
        loaded_model = get_model()
        return MetaResponse(**loaded_model.metadata())

    @app.post("/api/v1/predict", response_model=PredictResponse)
    async def predict(payload: PredictRequest) -> PredictResponse:
        """Score mutation/CNA evidence against detailed and tumor-level classes."""
        loaded_model = get_model()

        try:
            raw = loaded_model.predict(
                alterations=list(payload.alterations),
                top_k=payload.options.return_top_k,
                include_evidence=payload.options.include_evidence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        results = {
            level_name: PredictionLevelResult(**level_payload)
            for level_name, level_payload in raw["results"].items()
        }

        return PredictResponse(
            input_normalized=raw["input_normalized"],
            results=results,
            confidence=ConfidenceAssessment(**raw["confidence"]),
            tumor_to_detailed=raw["tumor_to_detailed"],
            notes=raw["notes"],
        )

    return app


app = create_app()
