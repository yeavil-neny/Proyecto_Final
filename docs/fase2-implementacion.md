# Fase 2 — Implementación y conexión del agente de devoluciones

**Proyecto Final — IA Generativa.** Caso de estudio: EcoMarket.
**Punto de partida obligatorio:** el sistema RAG del Taller Práctico #2.

---

## 1. Qué se implementó

La Fase 2 toma el sistema RAG del Taller #2 (Ruta informativa) y lo extiende con el agente de devoluciones (Ruta de acción), unidos por el router determinista de la Fase 1. La estructura del repositorio:

```
src/
  rag_ecomarket.py        Sistema RAG completo del Taller #2 — SIN CAMBIOS (ruta informativa)
  prompts.py              Plantillas del Taller #2 + nuevo prompt del agente (SYSTEM_AGENTE_ACCION)
  herramientas.py         Las 3 herramientas del agente y el motor de reglas de la política
  agente.py               Router determinista + agente LangChain + CLI de demo
  pruebas_fase2.py        Casos de prueba deterministas (sin LLM ni API key)
data/                     Corpus del Taller #2 + etiquetas_emitidas.json (registro auditable)
```

### 1.1 Conexión con el punto de partida

El RAG del Taller #2 no se reescribió: se reutilizó **como está** (mismos embeddings, misma base Chroma con similitud coseno, umbral 0.55 con k=4 y escalado honesto), y el agente reúne el mismo LLM (`ChatOpenAI` con endpoint OpenAI-compatible de Gemini) y la misma clave API. Continuidad que la propuesta (3.3) elegió como criterio.

**Nota de versión:** la propuesta mencionaba el par `create_tool_calling_agent`/`AgentExecutor` (API de LangChain 0.x). El entorno ejecuta **LangChain 1.x**, que los reemplazó por el constructor `create_agent` (mismo ciclo de decisión: el modelo elige herramienta y argumentos, el runtime ejecuta la función y alimenta al modelo hasta la respuesta final); la equivalencia queda registrada aquí.

### 1.2 El reloj simulado (decisión documentada)

El corpus está fijado a `fecha_base = 2026-09-17` (campo de `data/pedidos.json`). Las herramientas usan esa fecha como "hoy" para calcular los plazos de la política; si usaran la fecha real del sistema, todos los plazos del corpus estarían vencidos y ningún caso de demo sería positivo. La variable `RELOJ_SIMULADO` (ver `.env.example`) permite sobreescribirlo para pruebas.

---

## 2. Herramientas con su contrato JSON

Toda salida es JSON estructurado: `{exito: true/false, ...}`. El agente decide con datos, no con prosa; los mensajes de error están redactados como **instrucciones al agente** (qué pedirle al cliente, qué no hacer).

### 2.1 `buscar_pedido(tracking)`

| Contrato | Detalle |
|---|---|
| Entrada | `tracking` ECO-XXXXX (acepta texto alrededor, p. ej. "pedido ECO-10012") |
| Proceso | Búsqueda en `data/pedidos.json` (12 pedidos del caso) |
| Éxito | `{exito, pedido: {tracking, cliente, productos, total, estado, fecha_entrega, transportadora}}` |
| Fallos | `formato_invalido` (fuera del patrón), `pedido_no_encontrado` (inexistente) — ambos con instrucción al agente |

### 2.2 `verificar_elegibilidad_devolucion(tracking, producto, motivo)`

Aplica la política real (`data/politicas_devolucion.md`) con un **motor de reglas determinista** (auditable y reproducible), sobre tres datos: el pedido, la categoría del producto (inventario CSV) y el motivo del cliente.

| Regla del dictamen | Cuándo se dispara |
|---|---|
| `devolucion_ya_en_proceso` | El pedido ya tiene una devolución abierta (ECO-10007 del corpus) |
| `pedido_no_entregado` | El pedido no ha sido entregado: la política aplica desde la entrega |
| `excepcion_defecto` | Motivo = defecto/daño/incorrecto y ≤ 7 días desde la entrega (aplica a CUALQUIER categoría — sección "Excepciones") |
| `excepcion_defecto_fuera_de_plazo` | Motivo defecto pero > 7 días |
| `categoria_no_devoluble` | Categoría excluida por la política: Despensa (alimentos), Higiene (higiene y cuidado personal), semillas y plantas, personalizados, venta final |
| `fuera_de_plazo` | Producto devolvible pero > 30 días de la entrega |
| `motivo_no_clasificado` | El texto del cliente no se clasifica con certeza → `requiere_aclaracion: true`: el agente pregunta, no asume |
| `devolucion_estandar` | Producto devolvible, ≤ 30 días: elegible (con condiciones: sin usar, empaque original; el retorno lo asume el cliente sin defecto) |

| Fallos de contrato | Cuándo |
|---|---|
| `producto_requerido` / `motivo_requerido` | Faltó el dato; el mensaje enumera las opciones reales del pedido |
| `producto_no_encontrado_en_pedido` | El producto mencionado no pertenece al pedido |
| `producto_ambiguo` | Coincide con varios productos; se pide elegir |

### 2.3 `generar_etiqueta_devolucion(tracking, dictamen)`

| Contrato | Detalle |
|---|---|
| Entrada | `tracking` + `dictamen` (el JSON completo que devolvió la herramienta 2) |
| Validaciones | 1) el dictamen debe declarar `elegible: true` y corresponder al mismo tracking; 2) **re-verificación interna** de la elegibilidad antes de emitir (defensa en profundidad: no se confía en la síntesis del agente); 3) idempotencia: no emite dos veces el mismo pedido |
| Éxito | `{exito, etiqueta: {numero_etiqueta EL-XXX, numero_guia, transportadora, direccion_recepcion, enlace_pdf_simulado}}` |
| Fallos | `dictamen_invalido`, `no_elegible_o_dictamen_incoherente`, `elegibilidad_no_reproducible` (o el error del pedido) |
| Auditoría | Cada emisión se persiste en `data/etiquetas_emitidas.json` (fecha simulada, producto, regla aplicable, etiqueta) — insumo de la observabilidad de la Fase 3 |

---

## 3. El agente (LangChain 1.x) y su protocolo

- **Construcción:** `create_agent(llm, herramientas, system_prompt=SYSTEM_AGENTE_ACCION)`, reutilizando el LLM del Taller #2 (`ChatOpenAI` sobre el endpoint OpenAI-compatible de Gemini, temperatura 0.1).
- **Prompt del sistema** (`src/prompts.py`): mismo rol y tono de los talleres + protocolo de acción: no inventar datos (todo dato viene de una herramienta), pedir tracking/producto/motivo si faltan, pasar el dictamen **íntegro** a la etiqueta, nunca emitir etiqueta con dictamen negativo, explicar cada rechazo con la regla exacta, preguntar cuando el dictamen pide aclaración, y no prometer reembolsos (se aprueban al recibir y revisar el producto).

---

## 4. Evaluación del comportamiento (el discernimiento del agente)

### 4.1 Pruebas deterministas (sin LLM): `python src/pruebas_fase2.py`

**36 casos, todos PASAN** (resultado de la corrida completa):

| Grupo | Casos cubiertos |
|---|---|
| Router (11) | Órdenes con y sin tracking, imperativos, defecto + petición de etiqueta → **acción**; preguntas de estado, proceso, política, plazo, condicionales, saludo → **informativa** |
| `buscar_pedido` (5) | Éxito, rescate del patrón dentro de texto, formato inválido, inexistente, argumento vacío |
| `verificar_elegibilidad` (11) | Vía estándar elegible; defecto dentro/fuera de plazo; la excepción de defecto **alcanza categorías no devolvibles** (café defectuoso sí, café "no me gustó" no — contraste clave); pedido no entregado; devolución ya en proceso; semillas; motivo ambiguo pide aclaración; producto ajeno al pedido; producto y motivo vacíos |
| `generar_etiqueta` (7) | Emisión con dictamen válido; no duplicación; dictamen improvisado (**lo revalida y rechaza**); dictamen con `elegible=false` (**no emite**); tracking inexistente; registro auditable |

### 4.2 El "discernimiento" pedido por el enunciado

Se demuestra en tres niveles: (a) el **router** separa ejecutar de informar (4.1), (b) el **motor de reglas** distingue defecto de cambio de opinión y alcanza o niega la excepción según el plazo, y pide aclaración cuando no tiene certeza, y (c) el **agente LLM** decide cuándo llamar a cada herramienta y qué pedir al cliente.

**Corrida extremo a extremo con el LLM real (Gemini vía endpoint OpenAI-compatible, clave local en `.env`):**

| # | Consulta | Comportamiento observado |
|---|---|---|
| 1 | "quiero devolver los envases de vidrio del ECO-10005, ya no los necesito" | Ruta de acción → buscar → verificar (elegible, cambio de opinión) → **emite etiqueta** y cierra con condiciones (sin usar, costo del cliente, reembolso al pasar revisión) |
| 2 | "quiero devolver el cafe del ECO-10006, no me gusto" | **Rechazo explicado**: categoría no devoluble; cita la excepción (7 días, defecto) |
| 3 | "quiero devolver los envases de vidrio del ECO-10005" (sin motivo) | Busca el pedido y **pregunta el motivo** en lugar de asumirlo |
| 4 | "quiero devolver la vela del pedido ECO-10007, llego defectuosa" | Comunica que **ya hay una devolución en proceso**; no duplica etiqueta |
| 5 | "¿Cuando llega mi pedido ECO-10003?" | Router → ruta informativa (RAG); recuperados sin el propio pedido → **escalado honesto**, sin inventar |
| 6 | "me llego dañada la maquina de afeitar, quiero devolverla" (sin tracking) | **Pide el número de seguimiento** antes de actuar |
| 7 | ... del pedido ECO-99955 (inexistente) | Comunica que no existe y pide revisar el número |

### 4.3 Ajuste de transporte documentado: round-trip de firmas de pensamiento (Gemini 3.x)

Los modelos Gemini de la serie 3 exigen reenviar, en cada vuelta del bucle de herramientas, la *thought_signature* (firma de pensamiento) que ellos mismos entregan con cada llamada a función; sin ella la API responde 400. El cliente HTTP de langchain-openai descarta ese campo al reconstruir el historial. La solución (src/agente.py, clases `_ClienteConFirmas` y `ChatGeminiConFirmas`): un proxy del cliente HTTP que cosecha la firma de cada respuesta y la repone en la petición siguiente. El LLM de la ruta informativa no lo necesita (el RAG del Taller #2 no usa herramientas) y queda intacto.

---

## 5. Cómo ejecutar

**Diagrama de flujo del proceso de devolución** (router, decisiones del agente y llamadas a las herramientas): [`flujo-devolucion-agente.html`](flujo-devolucion-agente.html) — diagrama interactivo con tema claro/oscuro, zoom, búsqueda y rastreo de relaciones; el botón *Export* exporta PNG/SVG para el documento y el video (generado con Archify, validación completa: 9/9 checks, 0 errores, 0 advertencias).

```bash
# 1. Entorno: python 3.12+ con requirements.txt de este repo
# 2. Clave: copiar .env.example a .env y poner GEMINI_API_KEY

# Pruebas deterministas (NO requieren clave):
python src/pruebas_fase2.py

# Ruta de acción (agente):
python src/agente.py --consulta "quiero devolver los envases de vidrio del ECO-10005, ya no los necesito" --razonamiento
# caso de rechazo explicado:
python src/agente.py --consulta "quiero devolver el cafe del ECO-10006, no me gusto"
# caso de informar (ruta RAG intacta):
python src/agente.py --consulta "Cuando llega mi pedido ECO-10003?"

# Bucle interactivo (ambas rutas):
python src/agente.py --chat
```

---

## 6. Límites declarados de la fase (alimentan la Fase 3)

- Todo es simulado sobre los JSON/CSV del corpus; la "etiqueta" es un registro, no una guía real.
- Clasificar el motivo por palabras clave es frágil ante formulaciones fuera de las huellas — por eso el dictamen pide aclaración en lugar de asumir; con LLM en ejecución se evalúa si el agente lo pide bien.
- El router por reglas cubre las formulaciones de los casos probados; las reglas son auditables pero incompletas por definición (se discute en la Fase 3 con métrica de enrutamientos equivocados).
- Faltan en la fase 2: la prueba de discernimiento del agente LLM en vivo (requiere API key), y el análisis de riesgos/observabilidad.