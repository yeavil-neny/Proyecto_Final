# Proyecto Final — Agente de IA para Automatización de Tareas

**Curso:** IA Generativa — Unidad 3: Automatización de Tareas con IA Generativa
**Caso de estudio:** EcoMarket, e-commerce de productos sostenibles
**Equipo:** Cristian Humberto Yepes Marin y Yenny Alexandra Villarreal Suaza

Proyecto en construcción: extensión del asistente RAG del [Taller Práctico #2](https://github.com/yeavil-neny/IA_Generativa_Taller2_RAG) hacia un **agente de IA** capaz de ejecutar el proceso de devolución de productos de EcoMarket de forma autónoma (verificación de elegibilidad y generación de la etiqueta), desplegado en una interfaz web con Streamlit o Gradio.

## Estructura planeada

| Fase | Contenido |
|---|---|
| Fase 1 | Diseño de la arquitectura del agente: integración del RAG (router), definición de las herramientas y justificación del marco de agentes |
| Fase 2 | Implementación: herramientas como funciones, inicialización del agente, manejo de éxito/fallo, evaluación del comportamiento |
| Fase 3 | Análisis crítico: seguridad y ética, monitoreo y observabilidad, propuestas de mejora |
| Fase 4 | Despliegue: interfaz web (Streamlit o Gradio) y demostración funcional |

La documentación de cada fase quedará en `docs/` y el código en `src/`, siguiendo la estructura de los talleres anteriores. El punto de partida y las convenciones del equipo están resumidos en [`docs/estado-trabajo.md`](docs/estado-trabajo.md) (bitácora viva del proyecto).

## Progreso

| Fase | Documento | Estado |
|---|---|---|
| Propuesta preliminar | [`docs/propuesta-preliminar.md`](docs/propuesta-preliminar.md) | Lista |
| Fase 1 (arquitectura y herramienta) | [`docs/fase1-arquitectura.md`](docs/fase1-arquitectura.md) | Lista (con diagrama de flujo) |
| Fase 2 (implementación) | [`docs/fase2-implementacion.md`](docs/fase2-implementacion.md) | Implementada (agente + 3 herramientas + router; 36 casos deterministas pasan) |

**Código (`src/`):** `rag_ecomarket.py` y `prompts.py` son el sistema RAG del Taller #2 sin cambios (ruta informativa); `herramientas.py` define las 3 herramientas con contratos JSON; `agente.py` reúne el router determinista y el agente LangChain 1.x; `pruebas_fase2.py` ejecuta los casos de prueba sin llamar al LLM.