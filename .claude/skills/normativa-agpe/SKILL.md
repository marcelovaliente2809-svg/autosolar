---
name: normativa-agpe
description: Reglas regulatorias colombianas para autogeneración a pequeña escala (CREG 174 de 2021, Ley 1715/2099, UPME). Usar al modelar excedentes, liquidación, tarifas o incentivos tributarios.
user-invocable: false
---

# Reglas para el modelo (verificadas a oct-2026)

## Alcance
- AGPE: capacidad instalada ≤ 1 MW (Res. UPME 281 de 2015). Por encima es AGGE: fuera de alcance.
- Conexión al SIN, en sitio. Sin comunidades energéticas ni autogeneración remota.

## Excedentes (Res. CREG 174 de 2021, art. 25; Decreto 348 de 2017)
- Importación (Imp): energía que el usuario toma de la red en el periodo de facturación.
- Periodo de liquidación en el modelo: mes calendario. Exc1 = min(Exp, Imp); Exc2 = max(0, Exp − Imp).
- Exc1: créditos de energía, valor por kWh según la capacidad instalada:
  - AGPE ≤ 100 kW → CU − Cv (CU menos componente de comercialización).
  - AGPE > 100 kW (hasta 1 MW) → solo el componente G del CU (`tarifa.g_cop_kwh`).
- Exc2: excedentes por encima de Imp → se venden a `tarifa.precio_exc2_cop_kwh`
  (precio de bolsa horario, ver sección siguiente).
- Regla ≤/> 100 kW confirmada por el usuario; no hace falta preguntarla de nuevo.

## Cambio de precio de Exc2 (CREG 101 072 y 101 087 de 2025)
- 101 072 cambió la valoración de Exc2 de precio de bolsa horario a promedio ponderado de
  contratos (Mc).
- 101 087 lo dejó en transición: mientras la CREG no expida la metodología de traslado,
  se liquida con precio de bolsa horario.
- En el modelo: parámetro `tarifa.valoracion_exc2` = "precio_bolsa" (vigente) o "mc"
  (escenario futuro). Se comparan en sensibilidad.

## Incentivos tributarios (Ley 1715 de 2014 arts. 11-14, mod. Ley 2099 de 2021; Decreto 895 de 2022)
- Deducción de renta: 50 % de la inversión, repartible en hasta 15 años; cada año el valor
  deducido ≤ 50 % de la renta líquida antes de restar la inversión. Solo si declara renta.
- Exclusión de IVA y exención de aranceles en equipos: reduce el CAPEX (parámetro, no cálculo).
- Depreciación acelerada (art. 14).
- Alternativa (no acumular en el modelo base): descuento art. 255 ET, hasta 25 % de la inversión,
  solo personas jurídicas.
- Vigencia de beneficios: hasta el 10-jul-2051. Requieren certificado UPME (Res. UPME 135 de 2025).

## Fuentes
- CREG 174/2021 y 101 087/2025: gestornormativo.creg.gov.co
- Ley 1715 y 2099: actualicese.com, normograma DIAN
