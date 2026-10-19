---
name: nuevo-modulo
description: Implementa un módulo de src/autosolar a partir del contrato de su docstring, con tests. Úsalo con /nuevo-modulo <modulo> [notas].
argument-hint: "<modulo> [notas]"
disable-model-invocation: true
model: sonnet
effort: medium
---

Implementa el módulo `$0` de `src/autosolar/`. Notas extra del usuario: $ARGUMENTS

1. Lee `src/autosolar/$0.py` (el docstring es el contrato) y `src/autosolar/config.py`.
   Lee otros módulos solo si el contrato los usa como entrada.
2. Implementa exactamente las funciones del contrato. Docstrings cortos en español con
   unidades. Sin valores quemados: todo sale de la config.
3. Escribe `tests/test_$0.py` con casos pequeños calculables a mano (p. ej. 24 h, no 8760)
   y al menos una prueba de conservación o de límite.
4. Corre `pytest tests/test_$0.py` y `ruff check src/autosolar/$0.py`. Corrige hasta que pasen.
5. Responde en máximo 8 líneas: qué funciones quedaron, supuestos tomados y cualquier
   decisión que el usuario deba validar. No pegues el código en la respuesta.

Si el contrato es ambiguo en algo que cambia los resultados, pregunta antes de codificar.
