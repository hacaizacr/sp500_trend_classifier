"""Configuración del backend. Todo se controla con variables de entorno (o un archivo .env local).

Local  : MODEL_SOURCE=local  -> lee el modelo de la carpeta model/
AWS    : MODEL_SOURCE=s3     -> descarga el modelo desde S3 usando el ROL IAM de la instancia EC2
                                (no hay credenciales en el código).
"""
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # python-dotenv es opcional: si existe, carga el archivo .env
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    model_source: str          # "local" o "s3"
    local_model_dir: Path      # carpeta con el modelo cuando MODEL_SOURCE=local
    s3_bucket: str
    s3_prefix: str             # "carpeta" dentro del bucket, p. ej. "modelo/"
    aws_region: str
    cache_dir: Path            # donde se guardan los archivos descargados de S3
    frontend_dir: Path
    cors_origins: list


def get_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS", "*")
    return Settings(
        model_source=os.getenv("MODEL_SOURCE", "local").strip().lower(),
        local_model_dir=Path(os.getenv("LOCAL_MODEL_DIR", BASE_DIR / "model")),
        s3_bucket=os.getenv("S3_BUCKET", "").strip(),
        s3_prefix=os.getenv("S3_PREFIX", "modelo/").strip(),
        aws_region=os.getenv("AWS_REGION", "").strip(),
        cache_dir=Path(os.getenv("MODEL_CACHE_DIR", Path(tempfile.gettempdir()) / "modelo_cache")),
        frontend_dir=Path(os.getenv("FRONTEND_DIR", BASE_DIR / "frontend")),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
    )
