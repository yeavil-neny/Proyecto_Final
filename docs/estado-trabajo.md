# Estado de trabajo y contextos acordados del equipo

Este documento es el **cuaderno de bitácora del proyecto**: resume qué se ha hablado y decidido hasta la fecha, cómo está configurado el entorno y qué sigue. Se actualiza al final de cada sesión de trabajo para que cualquiera del equipo (o una IA de apoyo) retome el trabajo con el mismo contexto. **Nunca incluir claves API ni secretos aquí ni en ningún archivo del repositorio.**

---

## 1. Contexto general del curso

Proyecto Final de la asignatura **IA Generativa — Unidad 3: Automatización de Tareas con IA Generativa**.
Caso de estudio: **EcoMarket**, e-commerce de productos sostenibles (el mismo de todos los talleres).
Equipo: **Cristian Humberto Yepes Marin** y **Yenny Alexandra Villarreal Suaza**.

**Repositorios del curso:**
- Taller Práctico #1: https://github.com/yeavil-neny/IA_Generativa (asistente con plantillas de prompt y mini-RAG didáctico)
- Taller Práctico #2: https://github.com/yeavil-neny/IA_Generativa_Taller2_RAG (sistema RAG completo — **es el punto de partida obligatorio de este proyecto**)
- Proyecto Final: este repositorio

**Enunciado y rúbrica:** el PDF oficial está en la carpeta local `Documentacion/` (va en `.gitignore`, no se publica al repo). Resumen de las 4 fases y puntajes:

| Fase | Qué exige | Puntos |
|---|---|---|
| 1. Diseño de arquitectura y herramientas | Router o RAG-como-herramienta, mínimo **2 herramientas** (sin contar RAG), marco de agentes justificado, diagrama de flujo | 1.0 |
| 2. Implementación y conexión | Partir del código del Taller 2, herramientas como funciones, inicializar el agente, manejar éxito/fallo, probar discernimiento del agente | 2.0 |
| 3. Análisis crítico | Riesgos éticos/seguridad de agentes que actúan, monitoreo y observabilidad, propuestas de mejora | 1.0 |
| 4. Despliegue | Interfaz Streamlit o Gradio justificada, demo extremo a extremo | 1.0 |

**Entrega final:** link del repo con las 4 fases documentadas (formato Markdown, igual que los talleres) + **vídeo de máx. 10 minutos** (fase 1: 2–3 min herramientas; fase 2: 3–4 min arquitectura y código; fase 4: demo funcional 3–4 min).

---

## 2. Qué se ha hecho hasta hoy

1. **Repositorio creado y sincronizado** con la carpeta local (`main`, público). `Documentacion/`, `.env`, `chroma_*` y `__pycache__` van en `.gitignore`, siguiendo el patrón del Taller 2.
2. **Propuesta preliminar publicada** en `docs/propuesta-preliminar.md` (commit `249e8fa`), hecha para la sesión 5 según la agenda de Intu: objetivo del sistema, justificación del problema, enfoque de solución y referencias (Taller 1 y 2, clases 4–5, lecturas AWS/Activepieces/Intel).
3. **Sesión 5 pendiente de feedback:** llevar la propuesta a la conversación con el profesor y traer la retroalimentación para ajustar antes de codificar.

## 3. Decisiones de diseño ya tomadas (y su por qué)

| Decisión | Elección | Justificación resumida |
|---|---|---|
| Arquitectura | **Router con reglas de entrada deterministas** (el RAG del Taller 2 queda como ruta alterna, intacto) | Determinismo (el flujo más frecuente conserva el pipeline ya calibrado: umbral 0.55, k=4, escalado honesto) y seguridad (las herramientas que escriben datos solo son alcanzables por la ruta de devolución) |
| Herramientas (3, mínimo exigido: 2) | `buscar_pedido`, `verificar_elegibilidad_devolucion`, `generar_etiqueta_devolucion` | Simuladas sobre los archivos de datos del Taller 2; contratos con entrada validada y salida JSON estructurada (auditable, alimenta la fase de observabilidad) |
| Marco de agentes | **LangChain** | Continuidad total con el Taller 2 (Chroma, HuggingFaceEmbeddings, ChatOpenAI con endpoint OpenAI-compatible de Gemini); LlamaIndex descartado porque la base vectorial ya existe |
| Interfaz (Fase 4) | **Pendiente**: Streamlit o Gradio (se justifica en su momento) | El enunciado pide justificar la elección en la fase  |
| Datos | Reutilizar `data/` del repositorio del Taller 2 (política, 12 pedidos, 18 SKUs, 12 FAQs) | Coherencia con el enunciado ("partir del código del taller anterior") |

## 4. Entorno y cómo trabajar cada quien

1. **Clonar** este repo y el repo del Taller 2.
2. **Clave API Gemini:** cada quien genera la suya en https://aistudio.google.com/apikey y la pone en un archivo `.env` local (nunca en el repo ni en documentos). Ver `.env.example` del Taller 2 como plantilla. ⚠️ Nota: una clave quedó expuesta en `Documentacion/apuntes-taller2.docx` del Taller 2 — revocarla si sigue activa.
3. **Dependencias:** las de `requirements.txt` del Taller 2 (langchain, chromadb, sentence-transformers, etc.); se copiarán/ajustarán a este repo cuando arranque la fase 2.
4. **Para correr el RAG de referencia:** `cd` al repo del Taller 2 y `python src/rag_ecomarket.py` (instrucciones completas en su README y modo Colab).

## 5. Convenciones acordadas (las mantenemos en todas las fases)

- **Commits:** mensajes en español, **sin signos de tildes** (evita problemas de codificación, como en los talleres), con el usuario git propio del integrante y **sin atribución de IA** en el mensaje.
- **Documentación en lenguaje llano:** evitar jerga poco común (p. ej. se acordó no usar "corpora"); definir entre paréntesis las siglas la primera vez que aparecen (p. ej. HNSW — *Hierarchical Navigable Small World*).
- **Material de curso fuera del repo:** la carpeta `Documentacion/` (consigna, PDFs de clases) nunca se publica; el repo contiene solo la solución.
- **Privacidad:** ningún dato real de clientes ni secretos en el repo; el análisis de datos personales sigue la postura del Taller 1 (Ley 1581 de 2012).

## 6. Próximos pasos (checklist viva)

- [ ] Traer la retroalimentación del profesor de la sesión 5 y ajustar `docs/propuesta-preliminar.md` si aplica
- [ ] Fase 1 en docs: diagrama de flujo formal del proceso de devolución (con decisión del router y llamadas a herramientas)
- [ ] Fase 2: copiar el código base del Taller 2 a `src/`, definir las 3 herramientas con sus contratos JSON, inicializar el agente y diseñar los casos de prueba (uso de herramientas vs. respuesta directa, éxitos, fallos y escales)
- [ ] Fase 3: documento de análisis (riesgos éticos, monitoreo, observabilidad, mejoras)
- [ ] Fase 4: elegir Streamlit/Gradio justificadamente, construir la interfaz, grabar el vídeo de demo (guion: f1 2–3 min, f2 3–4 min, demo 3–4 min)
- [ ] Actualizar este archivo al final de cada sesión de trabajo

## 7. Registro de sesiones

| Fecha | Sesión | Lo avanzado |
|---|---|---|
| 2026-10-16 | Arranque del proyecto + propuesta preliminar | Repo creado y sincronizado (`main`). Leído el enunciado (`Documentacion/Proyecto Final.pdf`). Publicada `docs/propuesta-preliminar.md` (commit `249e8fa`) con las decisiones de diseño: router, 3 herramientas con contratos JSON, LangChain, interfaz a decidir en fase 4. Publicada esta bitácora (commit `d53bd0c`). Pendiente: feedback del profesor de la sesión 5 y arranque de la Fase 2. |