from pathlib import Path

import pytest
from pydantic import ValidationError

from autosolar.config import cargar_config

EJEMPLO = Path(__file__).parents[1] / "config" / "empresa_ejemplo.yaml"


def test_carga_config_ejemplo():
    cfg = cargar_config(EJEMPLO)
    assert cfg.empresa.nombre
    assert cfg.sistema_fv.kwp_max <= 1000


def test_rechaza_kwp_sobre_limite_agpe(tmp_path):
    texto = EJEMPLO.read_text(encoding="utf-8").replace("kwp_max: 1000", "kwp_max: 1500")
    ruta = tmp_path / "malo.yaml"
    ruta.write_text(texto, encoding="utf-8")
    with pytest.raises(ValidationError):
        cargar_config(ruta)
