# Fase 4 — Despliegue: interfaz web y demostración funcional

**Proyecto Final — IA Generativa.** Caso de estudio: EcoMarket.

---

## 1. Selección de la herramienta de interfaz: Streamlit

Se evaluaron las dos opciones del enunciado con los criterios que pide justificar (facilidad de uso y funcionalidad, más el costo de mantenimiento):

| Criterio | **Streamlit (elegida)** | Gradio |
|---|---|---|
| **Facilidad de uso (desarrollo)** | Interfaz escrita como un script Python lineal; una sola página, un solo archivo (`src/app_devoluciones.py`) | También script Python; dirigida a componentes de ML individuales |
| **Facilidad de uso (usuario final)** | Diseño de conversación claro (burbujas de chat), con espacio para el razonamiento del agente *sin* confundir al cliente en la conversación principal | Chat funcional, pero el diseño es monolítico; el detalle del razonamiento queda menos separable |
| **Funcionalidad requerida** | `st.session_state` da la conversación de varios turnos (el agente pregunta y el cliente responde en el turno siguiente); expanderes nativos muestran cada llamada de herramienta con su JSON — requisito de la demo — y el pie de firma muestra la ruta del router | `gr.Chatbot` cubre el chat; la visualización de razonamiento requiere componer componentes adicionales |
| **Costo de mantenimiento** | Cero servidor adicional: la app carga el agente y el RAG del propio repositorio con un `@st.cache_resource` único | Cero servidor adicional igualmente |
| **Continuidad del proyecto** | La misma pila Python del Taller #2 (requirements compartidos) | La misma pila igualmente |
| **Despliegue de la demo (aula)** | `streamlit run src/app_devoluciones.py` abre el navegador local | `gradio` también local |

**Decisión:** Streamlit, porque la funcionalidad diferencial de esta demo es *mostrar el razonamiento del agente* (qué ruta tomó el router, qué herramienta llamó, con qué argumentos y qué devolvió) sin sacarlo de la conversación: los expanderes de Streamlit lo resuelvan de forma nativa y comprensible en el video. Gradio habría servido para un chat simple, pero la demo del enunciado pide "algunos prompts específicos que demuestren el uso de herramientas y las distintas respuestas del agente" — exactamente el detalle que Streamlit expone con menos trabajo.

## 2. Implementación de la interfaz (`src/app_devoluciones.py`)

| Requisito del enunciado | Cómo se cumple |
|---|---|
| Campo de texto para el prompt del usuario | `st.chat_input` (conversación de chat con burbujas) |
| Área de visualización de la respuesta del agente | Burbuja del asistente con la respuesta final; y para transparencia: pie de firma con la ruta del router y expander "Razonamiento del agente" con cada llamada de herramienta (nombre, argumentos y salida en JSON legible); en la ruta informativa, expander "Detalle de la ruta" con las fuentes del RAG y su distancia coseno |
| Intuitiva | Botones de ejemplo en el margen (escenarios de demo de un clic), indicador de reinicio de conversación y aviso permanente de simulación educativa |
| Demo extremo a extremo | La misma conversación mantiene los turnos (el agente recuerda lo preguntado en el turno anterior); el registro de turnos JSONL sigue alimentando la observabilidad de la Fase 3 |

**Arranque verificado sin API:** la prueba `_build/arranque_interfaz.py` usa el framework de pruebas de Streamlit (`AppTest`) y confirma que la página construye el asistente (embeddings, base vectorial, agente), renderiza sin excepciones y deja el campo de consulta listo — sin gastar cuota del LLM.

## 3. Cómo ejecutar

```bash
# 1. Dependencias: requirements.txt (incluye streamlit>=1.49)
# 2. Clave: .env con GEMINI_API_KEY (ver .env.example)
streamlit run src/app_devoluciones.py
```

La primera carga tarda ~1 minuto (calcula los embeddings y arma la base vectorial: 50 chunks); las recargas siguientes reutilizan el agente ya construido. Sin la clave, la interfaz avisó con las instrucciones.

## 4. Guion de la demo funcional para el video (3–4 minutos)

Con la cuota diaria del LLM disponible (la corrida del 2026-10-23 agotó el Free Tier del día: 20 peticiones; alternar con la clave del otro integrante), la secuencia dentro de la interfaz:

| Momento | Consulta | Lo que muestra |
|---|---|---|
| 0:00–0:20 | — | Pantalla inicial: explicación de la arquitectura en el margen |
| 0:20–1:10 | "Quiero devolver los envases de vidrio del ECO-10005, ya no los necesito" | Éxito completo: router → agente → 3 herramientas → etiqueta; **abrir el expander del razonamiento** |
| 1:10–1:50 | "¿Cuál es el estado del pedido ECO-10003?" | Ruta informativa: RAG responde o escala con detalle de fuentes |
| 1:50–2:30 | "¿Qué productos no se pueden devolver?" | Segundo caso informativo (política con citas) |
| 2:30–3:10 | "Quiero devolver el café del ECO-10006, no me gustó" | Rechazo explicado con la regla exacta |
| 3:10–3:50 | "Quiero devolver los envases de vidrio del ECO-10005" y luego "llegó defectuosa" | Conversación de varios turnos: el agente pide el motivo y al recibirlo completa el flujo |
| Cierre | — | Mostrar `data/etiquetas_emitidas.json` y `data/registro_turnos.jsonl` (auditoría de demo) |

El video completo se divide entonces: herramientas de la Fase 1 con el diagrama de flujo de [`fase1-arquitectura.md`](fase1-arquitectura.md) (2–3 min), arquitectura y código de la Fase 2 con [`fase2-implementacion.md`](fase2-implementacion.md) (3–4 min) y esta demo (3–4 min).

## 5. Límites declarados de la fase

- La interfaz mantiene una conversación por pestaña del navegador (`st.session_state`); dos pestañas del mismo navegador comparten el agente construido pero no la conversación.
- Despliegue local para la demo del curso; el despliegue público (Streamlit Cloud u otro) queda como trabajo posterior — los archivos `.env` no viajan a un deploy: el proveedor recibe la clave por variable secretas.
- El reloj simulado sigue en la fecha del corpus (2026-09-17); quien quiera probar plazos distintos usa `RELOJ_SIMULADO` antes de lanzar Streamlit.