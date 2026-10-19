"""Carga y validación del archivo de configuración de una empresa (YAML)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

LIMITE_AGPE_KWP = 1000.0  # Res. UPME 281 de 2015: autogeneración a pequeña escala hasta 1 MW
LIMITE_AGPE_MENOR_KWP = 100.0  # CREG 174 de 2021: AGPE ≤ 0,1 MW vs. entre 0,1 y 1 MW


class Empresa(BaseModel):
    nombre: str
    declara_renta: bool = True


class Ubicacion(BaseModel):
    latitud: float = Field(ge=-90, le=90)
    longitud: float = Field(ge=-180, le=180)
    area_techo_m2: float = Field(gt=0)
    inclinacion_deg: float | None = Field(default=None, ge=0, le=90)  # None → max(|lat|, 10)


class Consumo(BaseModel):
    modo: Literal["sintetico", "archivo"]
    archivo: Path | None = None
    consumo_mensual_kwh: float | None = Field(default=None, gt=0)
    jornada: Literal["1_turno", "2_turnos", "continua"] = "1_turno"

    @model_validator(mode="after")
    def _revisar_modo(self) -> Consumo:
        if self.modo == "archivo" and self.archivo is None:
            raise ValueError("consumo.modo = 'archivo' requiere consumo.archivo")
        if self.modo == "sintetico" and self.consumo_mensual_kwh is None:
            raise ValueError("consumo.modo = 'sintetico' requiere consumo.consumo_mensual_kwh")
        return self


class Tarifa(BaseModel):
    operador_red: str
    nivel_tension: int = Field(ge=1, le=4)
    cu_cop_kwh: float = Field(gt=0)
    componente_comercializacion_cop_kwh: float = Field(ge=0)
    g_cop_kwh: float = Field(ge=0)  # componente G (generación) del CU
    escalamiento_anual: float = 0.0
    valoracion_exc2: Literal["precio_bolsa", "mc"] = "precio_bolsa"
    precio_exc2_cop_kwh: float = Field(ge=0)
    # Mc: precio con que se valoraría Exc2 en el escenario CREG 101 072/087 de 2025
    precio_mc_cop_kwh: float | None = Field(default=None, ge=0)


class SistemaFV(BaseModel):
    capex_cop_wp: float = Field(gt=0)
    opex_pct_capex: float = Field(ge=0)
    degradacion_anual: float = Field(ge=0, lt=0.05)
    perdidas_sistema: float = Field(ge=0, lt=1)
    kwp_min: float = Field(ge=0)
    kwp_max: float = Field(gt=0, le=LIMITE_AGPE_KWP)
    paso_kwp: float = Field(gt=0)
    m2_por_kwp: float = Field(gt=0)  # área de techo por kWp instalado


class Bateria(BaseModel):
    capex_cop_kwh: float = Field(gt=0)
    eficiencia_ciclo: float = Field(gt=0, le=1)
    dod: float = Field(gt=0, le=1)
    c_rate: float = Field(gt=0)
    vida_ciclos: int = Field(gt=0)
    vida_calendario_anios: int = Field(default=12, gt=0)  # reposición: lo primero entre ciclos y años
    kwh_min: float = Field(ge=0)
    kwh_max: float = Field(ge=0)
    paso_kwh: float = Field(gt=0)


class Finanzas(BaseModel):
    horizonte_anios: int = Field(gt=0, le=40)
    tasa_descuento: float = Field(gt=0)
    tasa_renta: float = Field(ge=0, lt=1)
    inflacion: float = 0.0
    renta_liquida_anual_cop: float = Field(gt=0)  # tope de la deducción: 50 % de este valor/año
    # Ley 2099 de 2021 / Decreto 895 de 2022: tasa de depreciación ≤ 33,33 % → mínimo 3 años
    anios_depreciacion: int = Field(default=3, ge=3)
    anios_depreciacion_normal: int = Field(default=10, gt=0)  # sin incentivos: ET art. 137
    incentivos_ley1715: bool = True  # deducción especial de renta (solo si declara_renta)


class Config(BaseModel):
    empresa: Empresa
    ubicacion: Ubicacion
    consumo: Consumo
    tarifa: Tarifa
    sistema_fv: SistemaFV
    bateria: Bateria
    finanzas: Finanzas


def cargar_config(ruta: str | Path) -> Config:
    """Lee un YAML de empresa y lo valida. Lanza pydantic.ValidationError si algo falla."""
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    return Config.model_validate(datos)
