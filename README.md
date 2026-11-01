# Proyecto Final — Agente de IA para Automatización de Tareas

**Curso:** IA Generativa — Unidad 4: Ingeniería de Software con Agentes y herramientas de próxima generación
**Caso de estudio:** EcoMarket, e-commerce de productos sostenibles
**Equipo:** Cristian Humberto Yepes Marin y Yenny Alexandra Villarreal Suaza

Proyecto Final del curso: extensión del asistente RAG del [Taller Práctico #2](https://github.com/yeavil-neny/IA_Generativa_Taller2_RAG) hacia un **agente de IA** capaz de ejecutar el proceso de devolución de productos de EcoMarket de forma autónoma (verificación de elegibilidad y generación de la etiqueta), desplegado en una interfaz web con Streamlit o Gradio.

## Estructura planeada

| Fase | Contenido | Documento | Estado |
|---|---|---|---|
| Propuesta preliminar | Entrega previa pedida en la plataforma Intu antes de la sesión 5 — **no hace parte de los entregables del enunciado del Proyecto Final** (se deja en el repo como antecedente del diseño) | [`docs/propuesta-preliminar.md`](docs/propuesta-preliminar.md) | Lista |
| Fase 1 | Diseño de la arquitectura del agente: integración del RAG (router), definición de las herramientas y justificación del marco de agentes | [`docs/fase1-arquitectura.md`](docs/fase1-arquitectura.md) | Lista (con diagrama de flujo) |
| Fase 2 | Implementación: herramientas como funciones, inicialización del agente, manejo de éxito/fallo, evaluación del comportamiento | [`docs/fase2-implementacion.md`](docs/fase2-implementacion.md) | Lista (agente + 3 herramientas + router; 36 casos deterministas + 7 en vivo con LLM) |
| Fase 3 | Análisis crítico: seguridad y ética, monitoreo y observabilidad, propuestas de mejora | [`docs/fase3-analisis-critico.md`](docs/fase3-analisis-critico.md) | Lista (riesgos y guardrails, monitoreo con registro JSONL, KPIs, mejoras priorizadas) |
| Fase 4 | Despliegue: interfaz web (Streamlit o Gradio) y demostración funcional | [`docs/fase4-despliegue.md`](docs/fase4-despliegue.md) | Lista (Streamlit justificado; `streamlit run src/app_devoluciones.py`; arranque verificado) — falta grabar el vídeo de demo |

**Código (`src/`):** `rag_ecomarket.py` y `prompts.py` son el sistema RAG del Taller #2 sin cambios (ruta informativa); `herramientas.py` define las 3 herramientas con contratos JSON; `agente.py` reúne el router determinista y el agente LangChain 1.x; `pruebas_fase2.py` ejecuta los casos de prueba sin llamar al LLM.