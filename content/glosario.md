# Glosario

## Sistema físico

| Término | Qué es | En el modelo |
| --- | --- | --- |
| kWp (kilovatio pico) | Potencia nominal de los paneles en condiciones estándar (1.000 W/m², 25 °C). Es el "tamaño" del sistema FV. | Variable de decisión del optimizador. |
| Rendimiento específico | Energía anual que produce 1 kWp instalado (kWh/kWp-año). | ≈1.446 kWh/kWp-año en Medellín (factor de planta ≈16,5 %). |
| Autoconsumo | Generación FV que la planta usa en el momento o después desde la batería, como % de la generación. | El kWh más valioso: reemplaza una compra al CU completo. |
| Importación | Energía que la planta toma de la red porque ni el sol ni la batería alcanzan. | Sobre todo de noche y en fines de semana. |
| Exportación | Generación FV que sobra y se entrega a la red. | Se divide en Exc1 y Exc2 al cierre del mes. |
| SOC (estado de carga) | Energía almacenada en la batería en cada hora (kWh). | Entre (1 − DoD) × capacidad y la capacidad. |
| DoD (profundidad de descarga) | Fracción de la capacidad que se puede usar sin dañar la batería. | 90 %: de 100 kWh se usan 90. |
| Eficiencia de ciclo | Fracción de la energía que entra a la batería y se recupera al descargarla. | Se reparte como √η en la carga y √η en la descarga. |
| Ciclo equivalente | Una descarga completa de la capacidad utilizable. Dos medias descargas = un ciclo. | Define cuándo se repone la batería. |
| C-rate | Potencia máxima de carga o descarga como fracción de la capacidad. | 0,5: una batería de 100 kWh entrega hasta 50 kW. |

## Tarifa: el CU y sus componentes

El **CU (costo unitario)** es lo que paga el usuario regulado por kWh. Es la suma de seis componentes que el operador de red publica cada mes por nivel de tensión: **CU = G + T + D + Cv + PR + R**.

| Componente | Qué remunera |
| --- | --- |
| G — generación | La energía en sí, comprada a los generadores. |
| T — transmisión | El uso de las redes de alta tensión del Sistema de Transmisión Nacional. |
| D — distribución | El uso de las redes locales del operador de red. |
| Cv — comercialización | Medición, facturación y atención al usuario. |
| PR — pérdidas | El costo de la energía que se pierde en las redes. |
| R — restricciones | Sobrecostos por limitaciones de la red. |

## Excedentes (Resolución CREG 174 de 2021)

| Término | Qué es | Cómo se valora |
| --- | --- | --- |
| AGPE | Autogenerador a pequeña escala: produce principalmente para su propio consumo, hasta 1 MW instalado (Res. UPME 281 de 2015). | Por encima de 1 MW es AGGE y aplican otras reglas. |
| Exc1 | Parte de lo exportado en el mes que **no supera** lo importado en ese mes. | Se permuta kWh por kWh contra la importación (crédito de energía). Si el sistema es ≤ 100 kW cada kWh vale **CU − Cv**; si es > 100 kW vale solo **G**. |
| Exc2 | Parte de lo exportado en el mes que **supera** lo importado. | Precio de bolsa horario (transición vigente, CREG 101 087 de 2025). A futuro: Mc. |
| Crédito de energía | Mecanismo de Exc1: lo exportado se descuenta de lo importado en el periodo de facturación. | Ver Exc1. |
| Precio de bolsa | Precio horario del mercado mayorista de energía, publicado por XM. | Valora Exc2 hoy. |
| Mc | Promedio ponderado de los precios de contratos del mercado mayorista. | Precio futuro de Exc2 según la CREG 101 072 de 2025, aún en transición. |

Ejemplo: si en un mes la planta importó 20 MWh y exportó 13 MWh, los 13 MWh son Exc1 y no hay Exc2. Si hubiera exportado 25 MWh, serían 20 MWh de Exc1 y 5 MWh de Exc2.

## Finanzas

| Término | Qué es | Cómo leerlo |
| --- | --- | --- |
| CAPEX | Inversión inicial: paneles, inversores, estructura, instalación y batería. | kWp × 1.000 × COP/Wp + kWh × COP/kWh. |
| OPEX | Costo anual de operación y mantenimiento. | % del CAPEX al año, ajustado por inflación. |
| VPN (valor presente neto) | Suma de todos los flujos de caja traídos a hoy con la tasa de descuento. | VPN > 0: rinde más que la tasa exigida. Es el criterio del optimizador. |
| Tasa de descuento | Rentabilidad mínima que exige la empresa (costo de capital o WACC). | Nominal anual. |
| TIR (tasa interna de retorno) | Tasa con la que el VPN da cero: la rentabilidad propia del proyecto. | Si supera la tasa de descuento, el proyecto conviene. |
| Payback simple | Años hasta que el flujo acumulado recupera la inversión, sin descontar. | — |
| Payback descontado | Lo mismo con flujos descontados. Siempre mayor que el simple. | — |
| LCOE (costo nivelado de energía) | Costo de producir cada kWh solar en la vida del sistema: (CAPEX + VP de OPEX y reposiciones) / VP de la energía generada. | Se compara con lo que vale cada kWh (CU, G, bolsa). |
| Escudo fiscal | Impuesto que se deja de pagar por un gasto deducible: tasa de renta × monto deducido. | Lo generan la depreciación y la deducción especial. |
| Depreciación acelerada | Ley 1715 art. 14 (mod. Ley 2099): tasa de hasta 33,33 % anual, es decir, 3 años. | Sin incentivos se deprecia en 10 años. |
| Deducción especial | Ley 1715 art. 11 (mod. Ley 2099): se resta de la renta el 50 % de la inversión, en hasta 15 años, con tope anual del 50 % de la renta líquida. | Requiere certificado UPME. |
| Reposición de batería | Compra de una batería nueva al cumplirse su vida en ciclos o en años, lo que ocurra primero. | — |
| Breakeven de batería | CAPEX de batería (COP/kWh) por debajo del cual la mejor solución incluye batería. | Indica cuánto tendría que bajar el precio para que convenga. |
