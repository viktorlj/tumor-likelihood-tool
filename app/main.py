"""FastAPI application for tumor likelihood predictions."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .profile_queries import (
    VALID_EVIDENCE_TYPES,
    VALID_SORT_OPTIONS,
    get_gene_list,
    query_gene_profile,
    query_tumor_profile,
)
from .schemas import (
    ConfidenceAssessment,
    GeneProfileItem,
    GeneProfileResponse,
    MetaResponse,
    PredictRequest,
    PredictResponse,
    PredictionLevelResult,
    ProfileItem,
    TumorProfileResponse,
)
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
            context={"title": "GENIE Tumor Likelihood Tool", "active_page": "home"},
        )

    @app.get("/tutorial", response_class=HTMLResponse)
    async def tutorial(request: Request) -> HTMLResponse:
        """Serve tutorial / reference guide page."""
        return templates.TemplateResponse(
            request=request,
            name="tutorial.html",
            context={"title": "How to Read the Results", "active_page": "tutorial"},
        )

    @app.get("/tumor-profile", response_class=HTMLResponse)
    async def tumor_profile_page(request: Request) -> HTMLResponse:
        """Serve tumor-type profile browsing page."""
        loaded_model = get_model()
        tumor_level = loaded_model.artifacts.levels["tumor"]
        tumor_types = [
            {
                "name": cls,
                "sample_count": tumor_level.sample_counts[i],
                "prior_probability": round(tumor_level.prior_probabilities[i], 4),
            }
            for i, cls in enumerate(tumor_level.classes)
        ]
        tumor_types.sort(key=lambda t: t["name"])
        return templates.TemplateResponse(
            request=request,
            name="tumor_profile.html",
            context={
                "title": "Tumor-Type Profile",
                "active_page": "tumor-profile",
                "tumor_types": tumor_types,
            },
        )

    @app.get("/gene-profile", response_class=HTMLResponse)
    async def gene_profile_page(request: Request) -> HTMLResponse:
        """Serve gene profile browsing page."""
        loaded_model = get_model()
        genes = get_gene_list(loaded_model.artifacts.evidence_tumor_df)
        return templates.TemplateResponse(
            request=request,
            name="gene_profile.html",
            context={
                "title": "Gene Profile",
                "active_page": "gene-profile",
                "genes": genes,
            },
        )

    @app.get("/api/v1/tumor-profile/{tumor_type}", response_model=TumorProfileResponse)
    async def tumor_profile_api(
        tumor_type: str,
        evidence_type: str = Query(default="mutation_allele"),
        sort_by: str = Query(default="fold_enrichment"),
        limit: int = Query(default=50, ge=1, le=500),
        include_subthreshold: bool = Query(default=False),
    ) -> TumorProfileResponse:
        """Return enrichment data for a specific tumor type."""
        loaded_model = get_model()
        tumor_level = loaded_model.artifacts.levels["tumor"]

        if tumor_type not in tumor_level.class_to_index:
            raise HTTPException(status_code=404, detail=f"Unknown tumor type: {tumor_type}")
        if evidence_type not in VALID_EVIDENCE_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid evidence_type. Must be one of: {VALID_EVIDENCE_TYPES}")
        if sort_by not in VALID_SORT_OPTIONS:
            raise HTTPException(status_code=422, detail=f"Invalid sort_by. Must be one of: {VALID_SORT_OPTIONS}")

        idx = tumor_level.class_to_index[tumor_type]
        items, total_sig = query_tumor_profile(
            loaded_model.artifacts.evidence_tumor_df,
            tumor_type=tumor_type,
            evidence_type=evidence_type,
            sort_by=sort_by,
            limit=limit,
            include_subthreshold=include_subthreshold,
        )

        return TumorProfileResponse(
            tumor_type=tumor_type,
            sample_count=tumor_level.sample_counts[idx],
            prior_probability=round(tumor_level.prior_probabilities[idx], 4),
            evidence_type=evidence_type,
            sort_by=sort_by,
            total_significant=total_sig,
            items=[ProfileItem(**item) for item in items],
        )

    @app.get("/api/v1/gene-profile/{gene}", response_model=GeneProfileResponse)
    async def gene_profile_api(
        gene: str,
        evidence_type: str = Query(default="mutation_gene"),
        sort_by: str = Query(default="fold_enrichment"),
        limit: int = Query(default=50, ge=1, le=500),
        include_subthreshold: bool = Query(default=False),
    ) -> GeneProfileResponse:
        """Return enrichment data for a specific gene across tumor types."""
        loaded_model = get_model()
        gene_upper = gene.upper()

        if evidence_type not in VALID_EVIDENCE_TYPES:
            raise HTTPException(status_code=422, detail=f"Invalid evidence_type. Must be one of: {VALID_EVIDENCE_TYPES}")
        if sort_by not in VALID_SORT_OPTIONS:
            raise HTTPException(status_code=422, detail=f"Invalid sort_by. Must be one of: {VALID_SORT_OPTIONS}")

        items, total_sig = query_gene_profile(
            loaded_model.artifacts.evidence_tumor_df,
            gene=gene_upper,
            evidence_type=evidence_type,
            sort_by=sort_by,
            limit=limit,
            include_subthreshold=include_subthreshold,
        )

        if not items and total_sig == 0:
            # Check if gene exists at all in the data
            has_gene = loaded_model.artifacts.evidence_tumor_df.filter(
                pl.col("gene") == gene_upper
            ).height > 0
            if not has_gene:
                raise HTTPException(status_code=404, detail=f"Gene not found: {gene_upper}")

        tumor_level = loaded_model.artifacts.levels["tumor"]
        sample_count_map = {
            cls: tumor_level.sample_counts[i]
            for i, cls in enumerate(tumor_level.classes)
        }

        return GeneProfileResponse(
            gene=gene_upper,
            evidence_type=evidence_type,
            sort_by=sort_by,
            total_significant=total_sig,
            items=[
                GeneProfileItem(
                    sample_count=sample_count_map.get(item["class_name"], 0),
                    **item,
                )
                for item in items
            ],
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
