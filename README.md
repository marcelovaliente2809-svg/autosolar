# autosolar

Evaluación técnico-económica de autogeneración solar con almacenamiento para usuarios
industriales en Colombia (AGPE ≤ 1 MW, CREG 174 de 2021, incentivos Ley 1715).

## Instalación

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Deben pasar 2 tests (validación de la configuración de ejemplo).

## Uso

1. Copia `config/empresa_ejemplo.yaml` y llénalo con los datos de la empresa.
2. (Cuando esté el motor) corre la optimización sobre ese archivo.

## Módulos

| Módulo | Qué hace |
| --- | --- |
| `config` | Lee y valida el YAML de la empresa |
| `solar` | Generación FV horaria por kWp (PVGIS) |
| `carga` | Perfil de consumo horario (archivo o sintético) |
| `balance` | Balance hora a hora con batería |
| `liquidacion` | Exc1, Exc2 y ahorro según CREG 174 |
| `finanzas` | Flujo de caja, incentivos, VPN, TIR, LCOE |
| `optimizacion` | Tamaño óptimo de FV y batería |
| `sensibilidad` | Tornado y escenarios regulatorios |
