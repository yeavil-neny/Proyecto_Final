# Propuesta preliminar — Agente de IA para Automatización de la Devolución de Productos

**Proyecto Final — IA Generativa.** Caso de estudio: EcoMarket (e-commerce de productos sostenibles).
**Equipo:** Cristian Humberto Yepes Marin y Yenny Alexandra Villarreal Suaza.

---

## 1. Objetivo del sistema

Extender el asistente de atención al cliente de EcoMarket, construido sobre un sistema RAG en el Taller Práctico #2, con un **agente de IA capaz de ejecutar acciones de forma autónoma**: automatizar el proceso de devolución de productos, que incluye la **verificación de la elegibilidad** del producto y la **generación de la etiqueta de devolución**, y desplegar la solución en una interfaz web simple donde un usuario final interactúe en lenguaje natural.

Al finalizar el proyecto, un cliente de EcoMarket podrá escribir en la interfaz, por ejemplo, *"quiero devolver el vela aromática del pedido ECO-10007, llegó defectuosa"*, y el sistema: (a) identificará que es una solicitud de acción y no una simple consulta, (b) verificará si el producto es elegible según la política real de la empresa, (c) generará la etiqueta de devolución con su guía e instrucciones si corresponde, (d) explicará con claridad el resultado — tanto el éxito como el rechazo con su motivo — y (e) escala a un asesor humano cuando el caso lo amerite. La misma interfaz seguirá respondiendo las consultas informativas (estado de pedidos, plazos, precios, catálogo) con el RAG ya construido.

## 2. Justificación del problema

- **El asistente actual solo informa; no actúa.** En el Taller #2 el sistema recupera y cita información (estados, fechas, plazos, reglas), pero si el cliente quiere *hacer* algo (iniciar una devolución) el sistema solo documenta el proceso y termina ofreciendo escalar a un asesor humano. La devolución sigue dependiendo del 20% de tickets que el planteamiento original del caso decía que caen sobre los asesores humanos.
- **La devolución es el proceso ideal para agenticar** en este caso: es el flujo con reglas verificables de negocio (la política de devoluciones ya está modelada en la base de conocimiento), produce un resultado tangible (etiqueta con guía de retorno) y su decisión es auditable paso a paso. La semana 4 del curso (agentes y workflows) define la distancia entre asistente y agente en exactamente esta línea: el asistente *responde*, el agente *realiza acciones end-to-end* eligiendo y encadenando herramientas.
- **Valor organizacional:** automatizar devoluciones reduce el tiempo de gestión de cada ticket con retorno, libera a los asesores para casos complejos y estandariza la aplicación de la política (menos decisiones subjetivas y menos errores humanos al citar reglas).
- **Continuidad real:** el sistema actual no se descarta; se amplía. La inversión del Taller #2 (embeddings, base vectorial, plantillas de prompt, umbral de pertinencia) es el núcleo informativo del agente.

## 3. Enfoque de solución con IA generativa

### 3.1 Arquitectura: router + agente con herramientas, donde el RAG es una ruta alterna

La arquitectura propuesta es una **arquitectura router**: la consulta del cliente entra por una capa de decisión que, por reglas de entrada deterministas, la enruta hacia dos subsistemas:

```
                       Consulta del cliente (lenguaje natural, interfaz web)
                                        |
                    +-------------------+-------------------+
                    |                                       |
              Ruta informativa                        Ruta de acción
        (detectada por: consulta/s                   (detectada por: intención
         de datos, sin intención                     de devolución: verbos de
         de ejecutar una acción)                     devolución + producto/tracking)
                    |                                       |
                    v                                       v
        [RAG del Taller #2, sin cambios]      [AGENTE con herramientas]
        Recuperación semántica top-k          1. buscar_pedido(tracking)
        sobre ChromaDB (coseno),              2. verificar_elegibilidad_devolucion(tracking, motivo)
        umbral de pertinencia 0.55;           3. generar_etiqueta_devolucion(tracking) — si es elegible
        si nada supera el umbral,             responde al cliente: éxito (etiqueta + guía) o
        mensaje honesto + escalamiento        rechazo explicado con la regla, o escalamiento
                    |                                       |
                    +-------------------+-------------------+
                                        |
                                Respuesta al cliente
```

**Por qué router y no "RAG como herramienta del agente".** Se evaluaron ambas opciones que admite el enunciado:

| Criterio | Router (elegida) | RAG como herramienta del agente |
|---|---|---|
| Determinismo | Las consultas informativas conservan el pipeline calibrado del Taller #2 (umbral, k, escalado) sin depender de que el LLM decida bien llamar a la herramienta | La calidad depende de que el agente decida usar RAG en cada consulta informativa: riesgo añadido en el flujo más frecuente |
| Seguridad | Las herramientas de acción (y la escritura de datos) solo son alcanzables por la ruta de devolución: un "deseo" mal inferido no puede escribir en el sistema | El agente decide si toca las herramientas de acción en cualquier consulta: superficie de riesgo mayor |
| Simplicidad de verificación | Cada ruta se prueba por separado (se reutilizan los casos del Taller #2) y el video demuestra ambas claramente | Un solo agente multi-herramienta es más flexible pero más difícil de auditar caso por caso |

El router se implementa con **reglas de entrada explícitas** (detección de intención de devolución por patrones de la consulta, más validaciones estructurales como el número de seguimiento), no con un clasificador LLM adicional: la decisión de enrutamiento es barata, auditable y reproducible, y la decisión *semántica* (elegibilidad, explicación al cliente) queda donde corresponde — en las herramientas y en el LLM.

### 3.2 Herramientas del agente (funciones simuladas, mínimo dos sin contar el RAG)

| # | Herramienta | Entrada | Proceso (simulado) | Salida |
|---|---|---|---|---|
| 1 | `buscar_pedido` | `tracking` (ECO-XXXXX) | Búsqueda en el registro de pedidos (JSON local) | Pedido completo (productos, estado, fechas) o error "pedido no encontrado" |
| 2 | `verificar_elegibilidad_devolucion` | `tracking` + `producto` + `motivo` (texto libre) | Aplica las reglas de la política de EcoMarket sobre el pedido (categorías no devolvibles, plazos, excepción por defecto de fábrica); interpreta el motivo con el LLM solo si hace falta clasificarlo | Dictamen estructurado: {elegible: bool, regla_aplicable, detalle, dias_restantes si aplica} |
| 3 | `generar_etiqueta_devolucion` | `tracking` + dictamen de elegibilidad | Simula la emisión de la guía: genera número de etiqueta y dirección de devolución; persiste el registro en un JSON de "etiquetas emitidas" (auditable) | Etiqueta: {numero_etiqueta, numero_guia, transportadora, direccion_recepcion, link_pdf_simulado} |

**Contratos documentados:** cada herramienta recibe entradas validadas (falla con error explícito si el argumento es inválido) y devuelve salidas estructuradas en JSON, de modo que el agente pueda decidir el siguiente paso (usar la etiqueta, rechazar, o preguntar al cliente) y que el registro de acciones sea auditable — requisito que alimenta directamente el análisis de observabilidad de la Fase 3.

**Manejo de errores previsto desde el diseño:** pedido inexistente o mal formateado (→ pedir el número de nuevo), producto no elegible (→ rechazo explicado con la regla exacta de la política, sin generar etiqueta), motivo ambiguo (→ preguntar al cliente en lugar de asumir), y caso del RAG fuera de dominio por la ruta informativa (→ escalamiento honesto ya implementado en el Taller #2).

### 3.3 Marco de agentes: LangChain

Se selecciona **LangChain** por continuidad y por ajuste al flujo: todo el componente informativo ya está en LangChain (Chroma, HuggingFaceEmbeddings, ChatOpenAI con el endpoint OpenAI-compatible de Gemini), así que el agente reúne su loop de decisión con `create_tool_calling_agent`/`AgentExecutor` (o equivalente con binding de funciones) reutilizando los mismos objetos y la misma clave API. LlamaIndex es muy fuerte en indexación, pero la base vectorial ya existe; reescribirla para usar otro marco añadiría trabajo sin beneficio para este problema. El criterio es el mismo de los talleres anteriores: corresponder la herramienta al trabajo real, no a la popularidad.

### 3.4 Despliegue (Fase 4) — decisión a justificar en su momento

La interfaz se construirá con **Streamlit o Gradio**; la elección definitiva se documenta en la Fase 4 con la comparación justificada que pide el enunciado (facilidad de uso, funcionalidad, costo de mantenimiento). Preliminarmente ambas encajan: campo de texto + área de respuesta + visualización del estado del agente (qué herramienta llamó y qué devolvió) para que el video muestre el razonamiento.

## 4. Referencias a conceptos, modelos y casos previos

**Dentro del curso (punto de partida):**
- Taller Práctico #1 ([repo](https://github.com/yeavil-neny/IA_Generativa)): caso EcoMarket, plantillas de prompt Rol→Contexto→Instrucciones→Restricciones, mini-RAG didáctico y análisis de privacidad (Ley 1581 de 2012).
- Taller Práctico #2 ([repo](https://github.com/yeavil-neny/IA_Generativa_Taller2_RAG)): sistema RAG con embeddings multilingües open-source, ChromaDB persistente con similitud coseno, umbral de pertinencia con escalado honesto, base de conocimiento de 4 tipos de documentos y experimento de control de alucinación.
- Clase 4 (AI Agents & Workflows): marco de herramientas de ampliación de conocimiento, reflection y agentic workflows; define la diferencia asistente/agente que este proyecto cruza.
- Clase 5 (Agentic Workforce, LLMOps y Hands-on n8n): agentes que orquestan sistemas externos; AgentOps como referencia para la fase de monitoreo.

**Referencias externas del curso para la sesión:**
- AWS, *Optimization in the era of generative AI* (2024): cómo la IA generativa automatiza y optimiza procesos reales de negocio, no solo respuestas.
- Activepieces, *Best generative AI automation techniques* (2024): técnicas de automatización accesibles (conectores, prompts, agentes) aplicables a un caso de PYME como EcoMarket.
- Intel Business, *Pivot to GenAI Automation* (2024): estrategias reales para integrar GenAI en flujos de trabajo existentes — el patrón "no se descarta el sistema actual, se amplía" que este proyecto sigue.

---

*Límites declarados del alcance preliminar: la simulación de las herramientas opera sobre los archivos de datos del Taller #2 (sin backend real); el análisis completo de riesgos éticos, la propuesta de observabilidad y la justificación final del marco de interfaz se documentan en las Fases 3 y 4 con el código ya en ejecución.*