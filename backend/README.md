# Backend FastAPI · Predicción de rendimiento relativo vs RSP (Grupo 2)

API que carga el **Random Forest** del Avance II y devuelve la probabilidad de que una acción del S&P 500
supere al ETF RSP en los próximos 12 meses. **Sirve también el frontend** desde la misma aplicación
(carpeta `frontend/`), tal como pide la actividad: un solo servicio, sin Nginx ni servidores extra.

```
backend/
├── app/
│   ├── main.py          # FastAPI: rutas /api/* y servicio del frontend
│   ├── service.py       # lógica de predicción (fila de entrada, advertencias, interpretación)
│   ├── model_store.py   # carga del modelo: local (model/) o desde S3
│   ├── schemas.py       # validación de entrada/salida
│   └── config.py        # variables de entorno
├── frontend/            # <- AQUÍ trabaja quien haga el frontend (index.html, css, js)
├── model/               # modelo y metadatos (solo se usa en local; en AWS se lee de S3)
├── deploy/              # script de subida a S3, política IAM, servicio systemd
├── tests/
├── requirements.txt     # versiones exactas del modelo + FastAPI
└── .env.example
```

## 1. Ejecutar en local

Necesitas **Python 3.11, 3.12 o 3.13**. Desde la carpeta `backend/`:

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
# macOS / Linux
python3 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- App + frontend: http://localhost:8000
- Documentación interactiva (probar la API desde el navegador): http://localhost:8000/docs
- Estado: http://localhost:8000/api/health

Debe mostrar `"status": "ok"` y `"fuente_modelo": "local:..."`. Con `--reload` el servidor se reinicia al editar código Python; los archivos de `frontend/` solo requieren recargar el navegador.

> **Las versiones de `requirements.txt` no se deben cambiar.** El modelo se guardó con scikit-learn 1.6.1;
> con otra versión puede fallar o dar resultados distintos.

## 2. API (contrato para el frontend)

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/info` | Descripción del modelo, objetivo, lista de campos (etiqueta, unidad, rango típico, tipo), sectores, métricas y metadatos del protocolo de evaluación. **Úsalo para armar la página principal y el formulario.** |
| GET | `/api/ejemplo` | Un caso válido (botón «Cargar ejemplo»). |
| POST | `/api/predict` | Devuelve la predicción. |
| GET | `/api/health` | Estado y origen del modelo (local o S3). |

### `POST /api/predict`

Entrada (JSON):

```json
{
  "Revenue_Growth": 8.0,
  "Net_Income": 1500,
  "Profit_Margin": 12.0,
  "Debt_to_Equity": 0.9,
  "PE_Ratio": 22.0,
  "Sector": "Information Technology",
  "Patrimonio_Negativo": false,
  "Perdidas": false
}
```

| Campo | Tipo | Unidad / nota |
|---|---|---|
| `Revenue_Growth` | número | % de crecimiento de ingresos |
| `Net_Income` | número | millones de USD (puede ser negativo) |
| `Profit_Margin` | número | % |
| `Debt_to_Equity` | número | ratio deuda/patrimonio |
| `PE_Ratio` | número | ratio precio/utilidad |
| `Sector` | texto | uno de `sectores` de `/api/info` (11 sectores GICS) |
| `Patrimonio_Negativo` | booleano, opcional | por defecto `false` |
| `Perdidas` | booleano, opcional | si se omite se infiere (`Net_Income < 0`) |

Los 5 indicadores pueden enviarse como `null`/omitirse (el modelo usa la mediana de entrenamiento y la API lo avisa), pero debe haber al menos uno. `Sector` es obligatorio.

Salida (ejemplo ilustrativo; los números dependen del modelo):

```json
{
  "modelo": "Random Forest",
  "probabilidad_supera": 0.5123,
  "probabilidad_no_supera": 0.4877,
  "probabilidad_supera_pct": 51.23,
  "prediccion": 1,
  "resultado": "Supera a RSP",
  "nivel": "incierto",
  "interpretacion": "Resultado incierto: probabilidad cercana al 50 %, sin evidencia predictiva fuerte.",
  "entrada_procesada": { "Revenue_Growth": 8.0, "...": "...", "Sector": "Information Technology" },
  "advertencias": [],
  "aviso_modelo": "Modelo con capacidad predictiva débil (ROC-AUC ~0.52)..."
}
```

- `nivel`: `favorable` (≥ 55 %), `desfavorable` (≤ 45 %) o `incierto` (entre 45 % y 55 %). Conviene mostrarlo con colores distintos.
- `advertencias`: textos listos para mostrar (campo vacío imputado, valor fuera del rango típico).
- Errores de validación: HTTP **422** con `detail` (sector inválido, tipo incorrecto, sin indicadores). Modelo no cargado: HTTP **503**.

## 3. Guía para quien haga el frontend

1. Poner los archivos en `frontend/` (`index.html` es el punto de entrada; puede reemplazarse por completo; el actual es solo una página mínima de ejemplo). Se admiten subcarpetas (`css/`, `js/`) y se sirven en `/css/...`, `/js/...`.
2. **Llamar siempre a la API con rutas relativas**: `fetch("/api/predict", ...)`.
   **Nunca** `http://localhost:8000/...`. Con rutas relativas el frontend funciona igual en local y en EC2 y la migración no requiere cambios.
3. Probar abriendo http://localhost:8000 (no abriendo el `.html` con doble clic: así `fetch` a `/api/...` no funcionaría).
4. Lo que pide la actividad: página principal que identifique el proyecto y explique qué predice (`/api/info` trae `proyecto`, `descripcion`, `que_predice`), formulario con los campos, y mostrar la predicción (probabilidad, resultado, interpretación y advertencias). La respuesta también incluye `metricas_prueba`, `entrenamiento` e `hiperparametros` para documentar las métricas y el esquema de validación temporal en la interfaz.

## 4. Migración a AWS (resumen para el equipo)

1. **S3**: crear el bucket y subir los 4 archivos de `model/` a `modelo/`:
   `./deploy/subir_a_s3.sh NOMBRE-BUCKET us-east-1` (o desde la consola web).
   Deben estar `modelo_rf_pipeline.joblib`, **`preprocesamiento.py`**, `metadata.json` y `ejemplo_entrada.json`.
2. **IAM**: crear una política con `deploy/iam-policy-s3-lectura.json` (cambiando el nombre del bucket), un **rol para EC2** con esa política y asociarlo a la instancia. No se escriben credenciales en el código.
3. **EC2**: Amazon Linux, grupo de seguridad con puerto **8000** abierto (y 22 para SSH). Copiar la carpeta `backend/` (sin `.venv` ni `model/`, que no hace falta), crear el entorno virtual e instalar `requirements.txt` como en el paso 1.
4. **Variables de entorno** en EC2 (ver `deploy/api-modelo.service`, que ya las incluye):
   `MODEL_SOURCE=s3`, `S3_BUCKET=...`, `S3_PREFIX=modelo/`, `AWS_REGION=...`.
5. **Arrancar**: `uvicorn app.main:app --host 0.0.0.0 --port 8000` (o con systemd usando `deploy/api-modelo.service`).
6. **Verificar**: `http://IP-PUBLICA-EC2:8000/api/health` debe mostrar `"fuente_modelo": "s3://..."`. Eso es la evidencia de que el modelo se lee de S3.
7. Al terminar las pruebas y la grabación: **detener la instancia EC2**.

## 5. Variables de entorno

| Variable | Por defecto | Descripción |
|---|---|---|
| `MODEL_SOURCE` | `local` | `local` (carpeta `model/`) o `s3` |
| `S3_BUCKET` | — | Nombre del bucket (obligatorio con `s3`) |
| `S3_PREFIX` | `modelo/` | Carpeta dentro del bucket |
| `AWS_REGION` | — | Región del bucket |
| `MODEL_CACHE_DIR` | carpeta temporal | Dónde se guardan los archivos descargados |
| `CORS_ORIGINS` | `*` | Solo relevante si el frontend se sirve desde otro origen; en EC2 puede quedar vacío |

## 6. Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| `/api/health` responde 503 y `Can't get attribute 'Winsorizer'` | Falta `preprocesamiento.py` junto al `.joblib` (en local, en `model/`; en AWS, en S3). |
| Error al cargar el `.joblib` o aviso de versión de scikit-learn | No se instalaron las versiones exactas de `requirements.txt`. |
| 503 `AccessDenied` / `NoCredentialsError` en EC2 | El rol IAM no está asociado a la instancia, o la política no cubre el bucket/prefijo. |
| 503 `NoSuchKey` | `S3_PREFIX` o nombre de archivos distintos a los subidos. |
| El frontend no llega a la API | Se usó `localhost:8000` en el código en vez de rutas relativas, o se abrió el HTML con doble clic. |

## 7. Pruebas (opcional)

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
