"""Backend FastAPI: sirve la API de predicción y también el frontend (carpeta frontend/).

Ejecutar en local:   python -m uvicorn app.main:app --reload --port 8000
Documentación:       http://localhost:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import service
from .config import get_settings
from .model_store import ModelBundle, cargar_modelo
from .schemas import PrediccionEntrada, PrediccionSalida

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """El modelo se carga UNA vez al arrancar (desde disco o S3), no en cada petición."""
    app.state.bundle = None
    app.state.error = None
    try:
        app.state.bundle = cargar_modelo(settings)
    except Exception as e:  # la app sigue viva para poder diagnosticar en /api/health
        logger.exception("No se pudo cargar el modelo")
        app.state.error = str(e)
    yield


app = FastAPI(
    title="Predicción de rendimiento relativo vs RSP (S&P 500)",
    description="API del Proyecto Integrador · Grupo 2. Estima la probabilidad de que una acción del S&P 500 "
                "supere al ETF RSP en los próximos 12 meses usando un Random Forest.",
    version="1.0.0",
    lifespan=lifespan,
)

# Solo hace falta si el frontend se sirve desde otro origen (p. ej. Live Server en otro puerto).
# Servido desde esta misma app (como pide la actividad) no se usa CORS.
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["*"])


def get_bundle(request: Request) -> ModelBundle:
    bundle = request.app.state.bundle
    if bundle is None:
        raise HTTPException(status_code=503, detail=f"Modelo no disponible: {request.app.state.error}")
    return bundle


@app.get("/api/health", tags=["Estado"])
def health(request: Request):
    """Para comprobar que el servicio está vivo y de dónde cargó el modelo (local o S3)."""
    b = request.app.state.bundle
    if b is None:
        raise HTTPException(status_code=503, detail=f"Modelo no disponible: {request.app.state.error}")
    return {"status": "ok", "modelo": b.meta["modelo"], "fuente_modelo": b.fuente,
            "cargado_en": b.cargado_en, "versiones": b.meta.get("versiones")}


@app.get("/api/info", tags=["Modelo"])
def info(b: ModelBundle = Depends(get_bundle)):
    """Descripción del modelo y de los campos de entrada (para armar el formulario y la página principal)."""
    return service.info_para_frontend(b.meta, b.ejemplo)


@app.get("/api/ejemplo", tags=["Modelo"])
def ejemplo(b: ModelBundle = Depends(get_bundle)):
    """Un caso de entrada válido, útil para pruebas o para un botón 'Cargar ejemplo'."""
    return b.ejemplo


@app.post("/api/predict", response_model=PrediccionSalida, tags=["Predicción"])
def predict(datos: PrediccionEntrada, b: ModelBundle = Depends(get_bundle)):
    """Recibe los indicadores de una empresa y devuelve la probabilidad de superar a RSP."""
    try:
        return service.predecir(b.pipeline, b.meta, datos.model_dump())
    except ValueError as e:                      # p. ej. sector inválido
        raise HTTPException(status_code=422, detail=str(e))


# El frontend se sirve desde la misma app. Se monta al final para que /api/* tenga prioridad.
if settings.frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")
