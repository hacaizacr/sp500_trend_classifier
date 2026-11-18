"""Pruebas de la API con TestClient (requiere httpx).  Ejecutar:  python -m pytest -q"""
from fastapi.testclient import TestClient

from app.main import app

EJEMPLO = {"Revenue_Growth": 8.0, "Net_Income": 1500, "Profit_Margin": 12.0,
           "Debt_to_Equity": 0.9, "PE_Ratio": 22.0, "Sector": "Information Technology"}


def test_endpoints():
    with TestClient(app) as c:          # 'with' ejecuta el arranque (carga del modelo)
        assert c.get("/api/health").json()["status"] == "ok"
        info = c.get("/api/info").json()
        assert "Information Technology" in info["sectores"]
        assert any(x["nombre"] == "Sector" for x in info["campos"])

        r = c.post("/api/predict", json=EJEMPLO)
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["probabilidad_supera"] <= 1
        assert body["resultado"] in ("Supera a RSP", "No supera a RSP")

        assert c.post("/api/predict", json={**EJEMPLO, "Sector": "Nada"}).status_code == 422   # sector inválido
        assert c.post("/api/predict", json={"Sector": "Energy"}).status_code == 422            # sin indicadores
        assert c.post("/api/predict", json={**EJEMPLO, "Foo": 1}).status_code == 422           # campo desconocido
        assert c.post("/api/predict", json={**EJEMPLO, "PE_Ratio": "abc"}).status_code == 422  # tipo inválido


def test_frontend_servido():
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
