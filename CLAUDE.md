# autosolar

Herramienta genérica en Python que dimensiona un sistema solar FV + baterías para una
empresa industrial colombiana (AGPE, ≤ 1 MW, conectada al SIN) y lo evalúa financieramente.
Trabajo del curso "Integración de FNCER a SEP". El usuario es ingeniero industrial.

## Estructura
- `config/*.yaml` → datos de cada empresa. El motor no tiene valores quemados.
- `src/autosolar/` → un módulo por etapa. El docstring de cada archivo es su contrato:
  léelo antes de implementar y no cambies la firma sin avisar.
  config → solar → carga → balance → liquidacion → finanzas → optimizacion → sensibilidad
- `tests/` → un `test_<modulo>.py` por módulo.
- `data/raw/` → descargas en caché (PVGIS, XM). No edites a mano. `data/processed/` → salidas.

## Convenciones
- Series horarias: `pd.Series` de 8760 valores, kWh por hora, año típico sin bisiesto.
- Unidades: kW, kWh, COP. Tasas en fracción (0.12, no 12).
- Nombres de dominio en español (`kwp`, `exc1`, `tarifa`), código PEP 8, ruff a 100 col.
- Funciones puras: reciben la config y devuelven datos; la E/S va solo en solar/carga.
- Reglas normativas (excedentes, incentivos): usa la skill `normativa-agpe`, no las inventes.

## Comandos
- Tests: `pytest`  · Lint: `ruff check src tests`
- Corre los tests del módulo que tocaste antes de dar la tarea por terminada.

## Compact instructions
Al compactar, conserva: módulo en curso, firmas acordadas, resultados de tests y decisiones
de modelado. Descarta salidas largas de comandos.
