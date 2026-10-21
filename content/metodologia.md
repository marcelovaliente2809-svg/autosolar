# Metodología

autosolar responde una pregunta: **¿cuánta potencia solar y cuánta batería le conviene instalar a una empresa para obtener el mayor valor presente neto (VPN) en 25 años, cumpliendo la regulación colombiana?**

Para responderla simula un año completo de la planta, hora por hora (8.760 horas), lo traduce a pesos y repite el cálculo para cada combinación de tamaños hasta encontrar la mejor. Es un **modelo de simulación horaria acoplado a una evaluación financiera, con optimización por búsqueda exhaustiva en una grilla de diseño**.

## Los siete pasos del cálculo

### 1. Recurso solar

Con la latitud, la longitud y la inclinación, la herramienta descarga de **PVGIS** (Centro Común de Investigación de la Comisión Europea) la potencia horaria de un sistema de 1 kWp durante varios años reales. La descarga ya incluye las sombras del relieve y las pérdidas del sistema.

- Se elige el **año real cuya energía anual está más cerca de la mediana**. No se promedian años, porque el promedio suaviza los días nublados y sesgaría el uso de la batería.
- La serie se pasa de UTC a hora local (huso = longitud ÷ 15; Colombia: UTC−5).
- Inclinación por defecto: el mayor entre |latitud| y 10° (por debajo de 10° el agua no escurre y el polvo se acumula). Orientación: sur.
- Resultado: 8.760 valores en kWh por kWp. Para Medellín: ≈ 1.446 kWh/kWp-año.

### 2. Consumo de la planta

- **Con datos de medidor:** se usa la serie horaria (o cada 15 minutos, agregada a horas).
- **Sin datos de medidor (perfil sintético):** se reparte el consumo mensual de la factura según la jornada:
  - *1 turno:* 7–17 h de lunes a viernes y 7–12 h los sábados; fuera de turno, carga base del 20 % del pico.
  - *2 turnos:* 6–22 h de lunes a sábado; carga base del 25 %.
  - *Continua:* 24 h todos los días, con un 10 % menos de noche.
  - Domingos y festivos de Colombia: solo carga base.
  - Cada mes se escala para sumar exactamente el consumo de la factura.

### 3. Balance energético horario

Para un tamaño dado (kWp, kWh de batería), en cada hora:

1. La generación solar cubre el consumo (**autoconsumo**).
2. Si sobra, se carga la batería hasta su límite y el resto se **exporta**.
3. Si falta, se descarga la batería y el resto se **importa** de la red.

La batería no se carga desde la red. Su energía utilizable está entre (1 − DoD) × capacidad y la capacidad; la eficiencia de ciclo se reparte como √η en la carga y √η en la descarga; la potencia está limitada por C-rate × capacidad.

### 4. Liquidación (Resolución CREG 174 de 2021)

Por cada mes calendario:

- **Importación (Imp)** = energía tomada de la red. **Exportación (Exp)** = energía entregada.
- **Exc1** = mín(Exp, Imp): se permuta como crédito de energía. Vale **CU − Cv** por kWh si el sistema es ≤ 100 kW, o solo **G** si es > 100 kW.
- **Exc2** = máx(0, Exp − Imp): se paga al precio de bolsa (regla vigente en transición, CREG 101 087 de 2025) o al Mc (escenario futuro, CREG 101 072 de 2025).
- **Ahorro** = factura sin sistema (consumo × CU) − factura con sistema (Imp × CU − Exc1 × valor del crédito − Exc2 × precio).

Cada kWh autoconsumido ahorra el CU completo. Por eso autoconsumir vale mucho más que exportar en sistemas grandes.

### 5. Evaluación financiera (25 años)

- **Año 0:** −CAPEX = kWp × 1.000 × COP/Wp + kWh × COP/kWh (sin IVA, por la exclusión de la Ley 1715).
- **Años 1 a 25:**
  - Ahorro del año 1, que crece con el escalamiento de la tarifa y baja con la degradación de los paneles.
  - Menos OPEX (porcentaje del CAPEX, ajustado por inflación).
  - Menos la reposición de la batería, al cumplir su vida en ciclos o en años, lo que ocurra primero.
- **Si la empresa declara renta:** el ahorro paga impuesto, y se aplican la depreciación acelerada (hasta 33,33 % anual, Ley 2099 y Decreto 895 de 2022) y la deducción especial del 50 % de la inversión (Ley 1715 art. 11: hasta 15 años, con tope del 50 % de la renta líquida). Sin incentivos, la depreciación es a 10 años.
- **Indicadores:** VPN, TIR, payback simple y descontado, y LCOE = (CAPEX + VP de OPEX y reposiciones) ÷ VP de la energía generada.

### 6. Optimización

Se repiten los pasos 3 a 5 para todas las combinaciones de la grilla, respetando el área del techo (kWp ≤ área ÷ m² por kWp) y el límite de 1 MW para autogeneración a pequeña escala (Res. UPME 281 de 2015). Se elige la combinación de **mayor VPN**. Se informan también la mejor sin batería y la mejor con batería.

### 7. Sensibilidad

- **Tornado:** variación de ±20 % en tarifa, CAPEX FV, CAPEX batería, tasa de descuento, escalamiento, degradación y precio de Exc2, una a la vez.
- **Escenarios:** se vuelve a optimizar con Exc2 al Mc, sin Ley 1715, y con jornadas de 2 turnos y continua.
- **Breakeven de batería:** precio (COP/kWh) por debajo del cual la mejor solución incluye batería.

## Cómo leer el resultado

- **LCOE frente a G.** Si producir un kWh solar (LCOE) cuesta menos que lo que reconocen por exportarlo (G), cada kWp adicional es rentable aunque se exporte, y el óptimo llena el techo. Si cuesta más, aparece un tamaño óptimo menor que el techo.
- **El techo de la batería.** Como el sol sale una vez al día, una batería hace como máximo un ciclo diario. Lo máximo que puede devolver cada kWh instalado es ≈ 365 × DoD × (CU × η − G) al año, traído a valor presente durante su vida. Si su precio supera ese valor, no se recomienda, sin importar la jornada.

## Validaciones

- **Recurso solar:** 1.446 kWh/kWp-año en Medellín, dentro del rango esperado para la ciudad (1.200–1.500), con el pico de producción cerca del mediodía solar.
- **Breakeven de batería:** la cuenta a mano (365 ciclos × 0,9 × (900 × 0,9 − 330) COP × factor de anualidad de 12 años al 12 %) da ≈ 0,98 M COP/kWh, igual al que obtiene la simulación horaria (≈ 1,0 M) con los parámetros de la versión inicial.
- **Conservación de energía:** en cada hora, carga = autoconsumo + descarga de batería + importación. Verificado en las pruebas automáticas.

## Supuestos y limitaciones

- **Usuario regulado.** Paga el CU publicado por el operador de red. Un usuario no regulado negocia su precio y sus reglas pueden ser distintas.
- **Usuario industrial sin contribución.** Los usuarios industriales registrados están exentos de la contribución de solidaridad del 20 %; un comercio pagaría CU × 1,2.
- **Precio único para Exc2.** La norma lo valora hora a hora; el modelo usa un promedio. No afecta los casos en que Exc2 es cero.
- **La batería no valora la confiabilidad.** El respaldo ante cortes de energía no entra en el VPN.
- **Un solo año solar representativo.** No se modela la variabilidad entre años (por ejemplo, años de El Niño).
- **Perfil de consumo sintético.** Sin datos de medidor, el consumo sigue un patrón idealizado.
- **Deducción especial y depreciación acelerada simultáneas.** Se asume que ambos beneficios se pueden usar al tiempo, porque están en artículos distintos de la Ley 1715.
- **Umbral de 100 kW.** Se compara contra los kWp de los paneles; algunos operadores de red usan la potencia AC del inversor.
- **Sin efecto fiscal de la reposición de batería.** Es un supuesto conservador.

## Valores de ejemplo y sus fuentes

Los valores precargados describen una planta ilustrativa en Medellín, no una empresa real. Reemplácelos con los datos de su empresa.

| Parámetro | Valor | Fuente |
| --- | --- | --- |
| CU nivel 1 (propiedad EPM) | 859 COP/kWh | [EPM, tarifas enero 2026](https://www.epm.com.co/content/dam/epm/clientes-y-usuarios/energia/tarifas-energia/Tarifas%202026/1.PublicacionTarifasEnero172026_ANT_OM.pdf) (suma de G, T, D, Cv, PR y R) |
| G (generación) | 296 COP/kWh | Ídem |
| Cv (comercialización) | 114 COP/kWh | Ídem |
| CAPEX FV, sistemas de 150–500 kWp | 3.450 COP/Wp | [DYC Ingenieros, 2026](https://dycingenieros.com/blog/energia-solar-para-empresas-colombia-cuanto-ahorra-2026): ≈ 3.300–3.600 COP/Wp |
| CAPEX batería comercial e industrial | 1.400.000 COP/kWh | [Solartodo, 2026](https://solartodo.com/knowledge/battery-energy-storage-system-pricing-trends-2026-utility-scale-ci-benchmarks): 290–450 USD/kWh en Latinoamérica |
| Recurso solar | PVGIS | [PVGIS, Comisión Europea](https://re.jrc.ec.europa.eu/pvg_tools/) |

## Marco normativo

- **Ley 1715 de 2014**, modificada por la **Ley 2099 de 2021**: fuentes no convencionales e incentivos tributarios.
- **Decreto 895 de 2022:** reglamenta los incentivos (depreciación acelerada hasta 33,33 % anual).
- **Resolución CREG 174 de 2021:** autogeneración a pequeña escala y reconocimiento de excedentes.
- **Resoluciones CREG 101 072 y 101 087 de 2025:** cambio del precio de Exc2 (bolsa → Mc) y su transición.
- **Resolución UPME 281 de 2015:** límite de 1 MW para autogeneración a pequeña escala.
- **Resolución UPME 135 de 2025:** certificación para acceder a los incentivos tributarios.
