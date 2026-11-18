"""Carga del modelo: desde disco (local) o desde Amazon S3 (AWS)."""
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import Settings

logger = logging.getLogger("app.model")

# preprocesamiento.py es obligatorio: contiene la clase Winsorizer que el .joblib necesita para reconstruirse.
ARCHIVOS_OBLIGATORIOS = ["modelo_rf_pipeline.joblib", "preprocesamiento.py", "metadata.json"]
ARCHIVOS_OPCIONALES = ["ejemplo_entrada.json"]


@dataclass
class ModelBundle:
    pipeline: object
    meta: dict
    ejemplo: dict
    fuente: str
    directorio: str
    cargado_en: str


def _descargar_desde_s3(s: Settings) -> Path:
    """Descarga los archivos del modelo a una carpeta de caché.
    Las credenciales NO se escriben en el código: boto3 usa la cadena por defecto
    (rol IAM de EC2 en la nube; `aws configure` o variables de entorno en local)."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    if not s.s3_bucket:
        raise RuntimeError("MODEL_SOURCE=s3 pero falta la variable S3_BUCKET.")
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    cliente = boto3.client("s3", region_name=s.aws_region or None)
    prefijo = s.s3_prefix.strip("/")

    for nombre in ARCHIVOS_OBLIGATORIOS + ARCHIVOS_OPCIONALES:
        clave = f"{prefijo}/{nombre}" if prefijo else nombre
        destino = s.cache_dir / nombre
        try:
            logger.info("Descargando s3://%s/%s", s.s3_bucket, clave)
            cliente.download_file(s.s3_bucket, clave, str(destino))
        except (ClientError, BotoCoreError) as e:
            if nombre in ARCHIVOS_OBLIGATORIOS:
                raise RuntimeError(
                    f"No se pudo descargar s3://{s.s3_bucket}/{clave}: {e}. "
                    "Revisa nombre del bucket, prefijo, región y los permisos del rol IAM."
                ) from e
            logger.info("Archivo opcional no encontrado en S3: %s", nombre)
    return s.cache_dir


def cargar_modelo(s: Settings) -> ModelBundle:
    import joblib
    import sklearn

    if s.model_source == "s3":
        carpeta = _descargar_desde_s3(s)
        fuente = f"s3://{s.s3_bucket}/{s.s3_prefix.strip('/')}"
    elif s.model_source == "local":
        carpeta = s.local_model_dir
        fuente = f"local:{carpeta}"
    else:
        raise RuntimeError("MODEL_SOURCE debe ser 'local' o 's3'.")

    faltan = [a for a in ARCHIVOS_OBLIGATORIOS if not (carpeta / a).exists()]
    if faltan:
        raise RuntimeError(f"Faltan archivos del modelo en {carpeta}: {faltan}")

    # Para que joblib encuentre `preprocesamiento.Winsorizer`
    if str(carpeta) not in sys.path:
        sys.path.insert(0, str(carpeta))

    meta = json.loads((carpeta / "metadata.json").read_text(encoding="utf-8"))
    version_entrenada = meta.get("versiones", {}).get("scikit-learn")
    if version_entrenada and version_entrenada != sklearn.__version__:
        logger.warning("scikit-learn instalado (%s) != el del entrenamiento (%s). "
                       "Instala la versión de requirements.txt.", sklearn.__version__, version_entrenada)

    pipeline = joblib.load(carpeta / "modelo_rf_pipeline.joblib")
    if not hasattr(pipeline, "predict_proba"):
        raise RuntimeError("El archivo cargado no es un clasificador con predict_proba().")

    ejemplo_path = carpeta / "ejemplo_entrada.json"
    ejemplo = json.loads(ejemplo_path.read_text(encoding="utf-8")) if ejemplo_path.exists() else {}

    logger.info("Modelo '%s' cargado desde %s", meta.get("modelo"), fuente)
    return ModelBundle(pipeline=pipeline, meta=meta, ejemplo=ejemplo, fuente=fuente,
                       directorio=str(carpeta), cargado_en=datetime.now().isoformat(timespec="seconds"))
