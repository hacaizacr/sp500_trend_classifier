"""Pruebas de la lógica con el modelo REAL de la carpeta model/.  Ejecutar:  python -m pytest -q"""
import pytest

from app.config import get_settings
from app.model_store import cargar_modelo
from app import service


@pytest.fixture(scope="module")
def bundle():
    return cargar_modelo(get_settings())


def test_prediccion_ejemplo(bundle):
    r = service.predecir(bundle.pipeline, bundle.meta, bundle.ejemplo)
    assert 0.0 <= r["probabilidad_supera"] <= 1.0
    assert abs(r["probabilidad_supera"] + r["probabilidad_no_supera"] - 1) < 1e-3
    assert r["nivel"] in {"favorable", "desfavorable", "incierto"}


def test_columnas_y_orden(bundle):
    fila = service.construir_fila(bundle.ejemplo, bundle.meta)
    assert list(fila.columns) == bundle.meta["features_orden"]
    assert fila[bundle.meta["columnas_sector"]].sum(axis=1).iloc[0] == 1


def test_perdidas_se_infiere(bundle):
    fila = service.construir_fila({"Net_Income": -100, "Sector": "Energy"}, bundle.meta)
    assert fila["Perdidas"].iloc[0] == 1


def test_campo_vacio_se_imputa(bundle):
    r = service.predecir(bundle.pipeline, bundle.meta, {**bundle.ejemplo, "PE_Ratio": None})
    assert 0.0 <= r["probabilidad_supera"] <= 1.0
    assert any("vacío" in a for a in r["advertencias"])


def test_sector_invalido(bundle):
    with pytest.raises(ValueError):
        service.construir_fila({**bundle.ejemplo, "Sector": "Inexistente"}, bundle.meta)
