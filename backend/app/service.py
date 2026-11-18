"""Lógica de predicción (sin dependencias de FastAPI, para poder probarla aparte)."""
import math

import numpy as np
import pandas as pd

ETIQUETAS = {
    "Revenue_Growth": "Crecimiento de ingresos",
    "Net_Income": "Utilidad neta",
    "Profit_Margin": "Margen de utilidad",
    "Debt_to_Equity": "Deuda / patrimonio",
    "PE_Ratio": "Ratio precio/utilidad (P/E)",
}


def _limpio(v):
    """float NaN -> None, numpy -> tipos nativos (para devolver JSON válido)."""
    if v is None:
        return None
    v = float(v)
    return None if math.isnan(v) else round(v, 6)


def construir_fila(payload: dict, meta: dict) -> pd.DataFrame:
    """Convierte los datos del formulario en 1 fila con las columnas y el orden del entrenamiento."""
    sector = (payload.get("Sector") or "").strip()
    if sector not in meta["sectores"]:
        raise ValueError(f"Sector no válido: '{sector}'. Opciones: {meta['sectores']}")

    fila = {c: np.nan if payload.get(c) is None else float(payload[c]) for c in meta["continuas"]}
    ni = fila["Net_Income"]
    if payload.get("Perdidas") is not None:
        fila["Perdidas"] = int(bool(payload["Perdidas"]))
    else:                                   # si no se indica, se infiere: utilidad neta negativa = pérdidas
        fila["Perdidas"] = int((not np.isnan(ni)) and ni < 0)
    fila["Patrimonio_Negativo"] = int(bool(payload.get("Patrimonio_Negativo") or False))
    for c in meta["columnas_sector"]:
        fila[c] = int(c == f"GICS Sector_{sector}")
    return pd.DataFrame([fila])[meta["features_orden"]]


def nivel_y_texto(p: float, meta: dict):
    b = meta["banda_incertidumbre"]
    if p >= 0.5 + b:
        return "favorable", "Mayor probabilidad de superar a RSP."
    if p <= 0.5 - b:
        return "desfavorable", "Mayor probabilidad de no superar a RSP."
    return "incierto", "Resultado incierto: probabilidad cercana al 50 %, sin evidencia predictiva fuerte."


def advertencias(payload: dict, meta: dict) -> list:
    """Avisos útiles para el usuario: campos vacíos y valores fuera del rango típico de entrenamiento."""
    avisos = []
    for c in meta["continuas"]:
        r = meta["rangos_entrenamiento"][c]
        v = payload.get(c)
        nombre = ETIQUETAS.get(c, c)
        if v is None:
            avisos.append(f"{nombre}: campo vacío; el modelo lo reemplaza por la mediana de entrenamiento ({r['mediana']:.2f}).")
        elif v < r["p1"] or v > r["p99"]:
            avisos.append(f"{nombre}: {v} está fuera del rango típico ({r['p1']:.2f} a {r['p99']:.2f}); "
                          "el modelo lo recorta a ese límite antes de predecir.")
    return avisos


def predecir(pipeline, meta: dict, payload: dict) -> dict:
    fila = construir_fila(payload, meta)
    p = float(pipeline.predict_proba(fila)[0, 1])
    nivel, texto = nivel_y_texto(p, meta)
    fila0 = fila.iloc[0]
    return {
        "modelo": meta["modelo"],
        "probabilidad_supera": round(p, 4),
        "probabilidad_no_supera": round(1 - p, 4),
        "probabilidad_supera_pct": round(p * 100, 2),
        "prediccion": int(p >= meta["umbral"]),
        "resultado": "Supera a RSP" if p >= meta["umbral"] else "No supera a RSP",
        "nivel": nivel,
        "interpretacion": texto,
        "entrada_procesada": {
            **{c: _limpio(fila0[c]) for c in meta["continuas"]},
            "Patrimonio_Negativo": bool(fila0["Patrimonio_Negativo"]),
            "Perdidas": bool(fila0["Perdidas"]),
            "Sector": payload["Sector"].strip(),
        },
        "advertencias": advertencias(payload, meta),
        "aviso_modelo": meta["advertencia"],
    }


def info_para_frontend(meta: dict, ejemplo: dict) -> dict:
    """Resumen del modelo para que el frontend construya el formulario y las explicaciones sin 'hardcodear' nada."""
    campos = []
    for c in meta["continuas"]:
        r = meta["rangos_entrenamiento"][c]
        campos.append({"nombre": c, "etiqueta": ETIQUETAS.get(c, c), "unidad": meta["unidades"].get(c, ""),
                       "tipo": "numero", "minimo_tipico": round(r["p1"], 2), "maximo_tipico": round(r["p99"], 2),
                       "mediana": round(r["mediana"], 2), "ejemplo": ejemplo.get(c)})
    campos.append({"nombre": "Sector", "etiqueta": "Sector GICS", "unidad": "", "tipo": "lista",
                   "opciones": meta["sectores"], "ejemplo": ejemplo.get("Sector")})
    campos.append({"nombre": "Patrimonio_Negativo", "etiqueta": "Patrimonio negativo", "unidad": "",
                   "tipo": "booleano", "opcional": True, "ejemplo": False})
    campos.append({"nombre": "Perdidas", "etiqueta": "La empresa tuvo pérdidas", "unidad": "",
                   "tipo": "booleano", "opcional": True,
                   "nota": "Si se omite, se infiere: utilidad neta negativa = pérdidas."})
    return {
        "proyecto": meta["proyecto"], "modelo": meta["modelo"], "descripcion": meta["descripcion"],
        "que_predice": meta["target"], "campos": campos, "sectores": meta["sectores"],
        "umbral": meta["umbral"], "banda_incertidumbre": meta["banda_incertidumbre"],
        "metricas_prueba": meta["metricas_prueba"], "advertencia": meta["advertencia"],
        # Metadatos adicionales para explicar el protocolo de evaluación en el frontend.
        "entrenamiento": meta.get("entrenamiento", {}),
        "hiperparametros": meta.get("hiperparametros", {}),
        "ejemplo": ejemplo,
    }
