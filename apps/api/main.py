from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.dossier.builder import DossierBuilder
from src.dossier.models import DrugDossier, OpenFDALabelEvidence
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore


class HealthResponse(BaseModel):
    status: str
    version: str


class DossierRequest(BaseModel):
    drug: str = Field(..., min_length=1)
    depth: int = Field(default=1, ge=1, le=3)
    max_edges: int = Field(default=75, ge=1, le=500)
    openfda_limit: int = Field(default=5, ge=1, le=25)
    include_openfda: bool = True


class LabelEvidenceRequest(BaseModel):
    rxcui: str = Field(..., min_length=1)
    name: str | None = None
    limit: int = Field(default=3, ge=1, le=25)


@lru_cache(maxsize=1)
def get_dossier_builder() -> DossierBuilder:
    """Return the default live-with-cache dossier builder."""

    return DossierBuilder(
        rxnorm_store=RxNormParquetStore(),
        openfda_store=OpenFDALabelStore(use_cache=True, allow_live=True),
    )


async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


async def build_dossier(
    request: DossierRequest,
    builder: DossierBuilder = Depends(get_dossier_builder),
) -> DrugDossier:
    return builder.build(
        request.drug.strip(),
        depth=request.depth,
        max_edges=request.max_edges,
        include_openfda=request.include_openfda,
        openfda_limit=request.openfda_limit,
    )


async def build_label_evidence(
    request: LabelEvidenceRequest,
    builder: DossierBuilder = Depends(get_dossier_builder),
) -> OpenFDALabelEvidence:
    return builder.openfda_store.get_label_evidence(
        request.rxcui.strip(),
        fallback_name=request.name.strip() if request.name else None,
        limit=request.limit,
    )


def create_app() -> FastAPI:
    api = FastAPI(
        title="rx-ray",
        description="Interactive drug dossier API",
        version="0.1.0",
    )
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api.add_api_route(
        "/health",
        health_check,
        methods=["GET"],
        response_model=HealthResponse,
    )
    api.add_api_route(
        "/dossier",
        build_dossier,
        methods=["POST"],
        response_model=DrugDossier,
    )
    api.add_api_route(
        "/label-evidence",
        build_label_evidence,
        methods=["POST"],
        response_model=OpenFDALabelEvidence,
    )
    return api


app = create_app()
