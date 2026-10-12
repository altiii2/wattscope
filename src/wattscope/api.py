"""HTTP endpoints and the local WattScope dashboard."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from wattscope.service import ForecastService

STATIC_ROOT = Path(__file__).resolve().parent / "static"


@lru_cache(maxsize=1)
def get_service() -> ForecastService:
    """Load artifacts lazily so a missing model does not prevent app startup."""
    root = Path(os.environ.get("WATTSCOPE_ROOT", Path(__file__).resolve().parents[2]))
    try:
        return ForecastService(root)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Forecast artifacts are unavailable. Prepare the dataset and train the model first.",
        ) from exc


Service = Annotated[ForecastService, Depends(get_service)]


class ForecastRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=128)
    origin: str | None = Field(default=None, max_length=64)

    @field_validator("client_id")
    @classmethod
    def strip_client_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("client_id must not be blank")
        return value

    @field_validator("origin")
    @classmethod
    def strip_origin(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("origin must not be blank; omit it to use the default window")
        return value


def _forecast(service: ForecastService, client_id: str, origin: str | None) -> dict[str, Any]:
    try:
        return service.forecast(client_id, origin)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="The requested client was not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail="Forecast artifacts are unavailable.") from exc


def create_app() -> FastAPI:
    app = FastAPI(
        title="WattScope API",
        description="Historical electricity forecasting with seasonal baselines and calibrated intervals.",
        version="1.0.0",
    )

    @app.get("/api/health", tags=["System"])
    def health() -> dict[str, str]:
        """Check HTTP liveness. Data readiness is reported by the data endpoints."""
        return {"status": "ok", "service": "WattScope"}

    @app.get("/api/overview", tags=["Forecasting"])
    def overview(service: Service) -> dict[str, Any]:
        try:
            return service.overview()
        except (FileNotFoundError, OSError) as exc:
            raise HTTPException(status_code=503, detail="Forecast artifacts are unavailable.") from exc

    @app.get("/api/clients", tags=["Forecasting"])
    def clients(service: Service) -> list[dict[str, Any]]:
        try:
            return service.clients()
        except (FileNotFoundError, OSError) as exc:
            raise HTTPException(status_code=503, detail="Forecast artifacts are unavailable.") from exc

    @app.get("/api/forecast", tags=["Forecasting"])
    def forecast_get(
        service: Service,
        client_id: Annotated[str, Query(min_length=1, max_length=128)],
        origin: Annotated[str | None, Query(max_length=64)] = None,
    ) -> dict[str, Any]:
        try:
            request = ForecastRequest(client_id=client_id, origin=origin)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="client_id and origin must not be blank.") from exc
        return _forecast(service, request.client_id, request.origin)

    @app.post("/api/forecast", tags=["Forecasting"])
    def forecast_post(request: ForecastRequest, service: Service) -> dict[str, Any]:
        return _forecast(service, request.client_id, request.origin)

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
    return app


app = create_app()
