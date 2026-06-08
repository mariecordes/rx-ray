from __future__ import annotations

import logging
import sys
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.dossier.builder import DossierBuilder
from src.dossier.models import DrugDossier, OpenFDALabelEvidence
from src.dossier.openfda_store import OpenFDALabelStore
from src.dossier.rxnorm_store import RxNormParquetStore
from src.query_answer.models import QueryAnswerResponse
from src.query_answer.service import QueryAnswerService
from src.query_understanding.models import QueryUnderstandingResponse
from src.query_understanding.service import QueryUnderstandingService

load_dotenv()


def configure_api_logging() -> None:
    """Ensure rx-ray API diagnostics are visible in the uvicorn console."""

    loggers = [
        logging.getLogger("src.query_understanding"),
        logging.getLogger("src.query_answer"),
    ]

    for logger in loggers:
        logger.setLevel(logging.INFO)
        has_handler = any(
            getattr(handler, "_rx_ray_api_handler", False)
            for handler in logger.handlers
        )
        if not has_handler:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
                )
            )
            handler._rx_ray_api_handler = True  # type: ignore[attr-defined]
            logger.addHandler(handler)

        logger.propagate = False


configure_api_logging()


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


class QueryUnderstandingRequest(BaseModel):
    query: str = Field(..., min_length=1)
    openfda_limit: int = Field(default=5, ge=1, le=25)


class QueryAnswerRequest(BaseModel):
    query: str = Field(..., min_length=1)
    openfda_limit: int = Field(default=5, ge=1, le=25)


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


async def understand_query(
    request: QueryUnderstandingRequest,
    builder: DossierBuilder = Depends(get_dossier_builder),
) -> QueryUnderstandingResponse:
    service = QueryUnderstandingService(builder=builder)
    return service.understand(
        request.query.strip(),
        openfda_limit=request.openfda_limit,
    )


async def answer_query(
    request: QueryAnswerRequest,
    builder: DossierBuilder = Depends(get_dossier_builder),
) -> QueryAnswerResponse:
    service = QueryAnswerService(builder=builder)
    return service.answer(
        request.query.strip(),
        openfda_limit=request.openfda_limit,
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
    api.add_api_route(
        "/query-understanding",
        understand_query,
        methods=["POST"],
        response_model=QueryUnderstandingResponse,
    )
    api.add_api_route(
        "/query-answer",
        answer_query,
        methods=["POST"],
        response_model=QueryAnswerResponse,
    )
    return api


app = create_app()
