"""Contratos de entrada y salida de la API (Pydantic v2). FastAPI los usa para validar y para generar /docs."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_NUM = dict(ge=-1e9, le=1e9, allow_inf_nan=False)

EJEMPLO = {"Revenue_Growth": 8.0, "Net_Income": 1500, "Profit_Margin": 12.0,
           "Debt_to_Equity": 0.9, "PE_Ratio": 22.0, "Sector": "Information Technology"}


class PrediccionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"example": EJEMPLO})

    Revenue_Growth: Optional[float] = Field(None, description="Crecimiento de ingresos, en %.", **_NUM)
    Net_Income: Optional[float] = Field(None, description="Utilidad neta, en millones de USD.", **_NUM)
    Profit_Margin: Optional[float] = Field(None, description="Margen de utilidad, en %.", **_NUM)
    Debt_to_Equity: Optional[float] = Field(None, description="Ratio deuda/patrimonio.", **_NUM)
    PE_Ratio: Optional[float] = Field(None, description="Ratio precio/utilidad.", **_NUM)
    Sector: str = Field(..., min_length=1, description="Sector GICS. Ver GET /api/info para las opciones.")
    Patrimonio_Negativo: Optional[bool] = Field(None, description="Opcional. Por defecto false.")
    Perdidas: Optional[bool] = Field(None, description="Opcional. Si se omite se infiere de Net_Income < 0.")

    @model_validator(mode="after")
    def _al_menos_un_indicador(self):
        if all(getattr(self, c) is None for c in
               ["Revenue_Growth", "Net_Income", "Profit_Margin", "Debt_to_Equity", "PE_Ratio"]):
            raise ValueError("Debes ingresar al menos uno de los 5 indicadores financieros.")
        return self


class PrediccionSalida(BaseModel):
    modelo: str
    probabilidad_supera: float = Field(..., description="P(la acción supera a RSP en 12 meses), de 0 a 1.")
    probabilidad_no_supera: float
    probabilidad_supera_pct: float
    prediccion: int = Field(..., description="1 = supera a RSP, 0 = no supera (umbral 50 %).")
    resultado: str
    nivel: str = Field(..., description="'favorable', 'desfavorable' o 'incierto' (banda 45 %-55 %).")
    interpretacion: str
    entrada_procesada: Dict[str, object]
    advertencias: List[str]
    aviso_modelo: str
