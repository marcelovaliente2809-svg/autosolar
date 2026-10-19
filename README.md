# autosolar

Evaluación técnico-económica de autogeneración solar con almacenamiento para usuarios
industriales en Colombia (AGPE ≤ 1 MW, CREG 174 de 2021, incentivos Ley 1715).

## Instalación

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[dev,api]"
pytest
```


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

## API (FastAPI)

`api/index.py` expone el motor por HTTP (es el backend del despliegue en Vercel: Next.js en la
raíz, Python en `api/`). Para correrla en local:

```bash
pip install -e ".[dev,api]"
uvicorn api.index:app --reload --port 8000
```

Documentación interactiva en <http://localhost:8000/api/docs>.

| Ruta | Body | Devuelve |
| --- | --- | --- |
| `GET /api/config-ejemplo` | — | `config/empresa_ejemplo.yaml` como JSON |
| `POST /api/optimizar` | `Config` | `mejor`, `mejor_sin_bateria`, `mejor_con_bateria`, `tabla` y `series` de la mejor |
| `POST /api/evaluar` | `{config, kwp, kwh_bat}` | la combinación (`resultado`) y sus `series` |
| `POST /api/sensibilidad` | `Config` | `tornado`, `escenarios` y `breakeven` de la batería |

```bash
curl localhost:8000/api/config-ejemplo > empresa.json
curl -X POST localhost:8000/api/optimizar -H "Content-Type: application/json" -d @empresa.json
```

- `series` trae `dia_habil` y `dia_domingo` (miércoles y domingo típicos de julio, 24 h),
  `balance_mensual`, `flujo_acumulado` (base y sin Ley 1715, con su payback) y
  `lcoe_vs_valores` (LCOE, CU, CU−Cv, G y precio Exc2).
- NaN e infinitos se devuelven como `null`. En `breakeven`, `estado` aclara si `null` significa
  `"siempre"` (conviene aun a 64× el CAPEX) o `"nunca"` (`0`).
- Un `Config` inválido responde 422 con el detalle de pydantic. El modo de consumo `archivo` no
  está disponible en la API (leería archivos del servidor): usa `sintetico`.
- La caché de PVGIS va a `data/raw/`; con la variable `AUTOSOLAR_CACHE_DIR` se cambia la carpeta
  (en Vercel, `/tmp`, porque el disco es de solo lectura).
- Los tests de la API no usan red (PVGIS se mockea): `pytest tests/test_api.py`.

## Frontend (Next.js)

Next.js (App Router, TypeScript, Tailwind) + Recharts en la raíz, con el patrón del template
`nextjs-fastapi` de Vercel: en desarrollo `next.config.ts` reescribe `/api/*` a uvicorn
(`127.0.0.1:8000`); en producción Vercel enruta `/api/*` a `api/index.py`. No hay rutas en
`app/api`.

```bash
npm install
npm run dev        # Next (localhost:3000) + uvicorn (puerto 8000) con concurrently
```

`npm run dev` usa el `python` del PATH: activa antes el entorno con las dependencias de la API.

| Carpeta | Qué tiene |
| --- | --- |
| `app/` | layout y página única (formulario + pestañas Resultados / Sensibilidad) |
| `components/` | formulario por secciones, KPIs, comparación y `graficas/` (una por archivo) |
| `lib/` | tipos de la API, campos del formulario, errores 422, formato es-CO y colores fijos |
