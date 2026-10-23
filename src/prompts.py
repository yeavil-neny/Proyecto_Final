# -*- coding: utf-8 -*-
"""
Plantillas de prompts del asistente de atención al cliente de EcoMarket,
versión Taller Práctico #2 (sistema RAG).

El asistente del Taller Práctico #1 usaba plantillas específicas por flujo
(pedido y devolución) con un mini-RAG didáctico: el código inyectaba el JSON
del pedido o la política completa como contexto. En este taller se generaliza
la plantilla para que atienda CUALQUIER consulta sobre la empresa, y el
contexto ya no se inyecta directamente: proviene del recuperador del sistema
RAG (los fragmentos más similares de la base de conocimiento), tras superar
una verificación de pertinencia.

La plantilla conserva los cuatro principios del Taller Práctico #1:

  1. ROL            -> define tono y comportamiento del modelo.
  2. CONTEXTO       -> los chunks recuperados por el RAG ("única fuente de
                       verdad"), precedidos de la etiqueta de tipo de
                       documento para que el modelo sepa de dónde proviene
                       cada dato.
  3. INSTRUCCIONES  -> qué debe incluir/hacer la respuesta, paso a paso,
                       incluida la regla de honestidad cuando el contexto no
                       alcanza para responder.
  4. RESTRICCIONES  -> qué NO puede hacer: ninguna alucinación, ningún dato
                       que no esté en el contexto, no revelar detalles
                       técnicos internos.

Las variables {{...}} se rellenan en rag_ecomarket.py antes de enviar el
prompt, con la misma función rellenar() del Taller Práctico #1.
"""

# ---------------------------------------------------------------------------
# Rol del sistema (system prompt de las versiones mejoradas del Taller #1,
# actualizado para el sistema RAG)
# ---------------------------------------------------------------------------

SYSTEM_AGENTE_ECOMARKET_RAG = """Actúa como un agente de servicio al cliente de EcoMarket, una tienda de e-commerce de productos sostenibles.

Reglas obligatorias:
- Usa EXCLUSIVAMENTE la información que aparece en el bloque de contexto. Si un dato no aparece ahí, di que no lo tienes y ofrece escalar el caso a un asesor humano; nunca lo inventes.
- Tono amable, cercano y breve. Tutea al cliente.
- Si la consulta trata sobre un pedido retrasado, empieza con una disculpa sincera y una breve explicación del motivo.
- Cierra ofreciendo ayuda adicional.
- Responde en español."""

# ---------------------------------------------------------------------------
# Plantilla general del sistema RAG (sustituye a las plantillas por flujo del
# Taller #1: ahora el contexto se recupera por similitud, no se elige en el
# código)
# ---------------------------------------------------------------------------

PROMPT_RAG = """Bloque de contexto recuperado de la base de conocimiento de EcoMarket (única fuente de verdad permitida; cada fragmento indica su tipo de documento):
---
{{contexto_rag}}
---

Consulta del cliente: "{{consulta_cliente}}"

Escribe la respuesta al cliente cumpliendo estas instrucciones:
1. Responde la consulta usando solo el bloque de contexto, citando fechas, precios, estados y nombres tal como aparecen.
2. Si la consulta menciona un número de seguimiento ECO-XXXXX, revisa primero si el bloque de contexto contiene ese pedido; si existe y aún no fue entregado (o el cliente pide rastrearlo), incluye el enlace de rastreo correspondiente: https://rastreo.ecomarket.co/ECO-XXXXX (reemplazando ECO-XXXXX por el número del pedido).
3. Si el contexto no contiene la información necesaria para responder, dilo con honestidad: explica que no dispones de esa información, ofrece escalar el caso a un asesor humano (canal de WhatsApp o correo de soporte) y no intentes completar la respuesta con conocimiento general.

Formato: 3 a 8 líneas, tono de chat, sin tablas ni encabezados."""

# ---------------------------------------------------------------------------
# Mensaje determinista cuando el RAG no recupera material pertinente: no se
# consulta al LLM y el asistente comunica con transparencia que no tiene las
# herramientas para atender la solicitud (comportamiento exigido por el
# enunciado del taller)
# ---------------------------------------------------------------------------

MENSAJE_SIN_HERRAMIENTAS = (
    "Gracias por escribir a EcoMarket. Revisamos nuestra base de conocimiento y "
    "no tengo la información ni las herramientas para atender esa solicitud. "
    "Puedo ayudarte con consultas sobre tus pedidos, devoluciones, catálogo, "
    "envíos, pagos y suscripciones. Si lo prefieres, te comunico con un asesor "
    "humano: WhatsApp 300 000 0000 (lunes a viernes, 8 a.m. a 6 p.m.) o "
    "soporte@ecomarket.co."
)

# ---------------------------------------------------------------------------
# Plantilla del modo control (--sin-rag / experimento B): misma consulta que
# el sistema RAG, pero sin ROL, sin CONTEXTO y sin RESTRICCIONES. Es el
# equivalente del flag --basico del Taller Práctico #1: aísla la variable
# que se modifica (el sistema RAG completo) y evidencia qué pasa cuando el
# modelo responde solo con su conocimiento general
# ---------------------------------------------------------------------------

PROMPT_SIN_RAG = """Responde como asistente de atención al cliente de EcoMarket.

Consulta del cliente: "{{consulta_cliente}}"
"""

# ---------------------------------------------------------------------------
# Mapeo de variables de cada plantilla (documentación del contrato)
# ---------------------------------------------------------------------------
VARIABLES = {
    "PROMPT_RAG": ["contexto_rag", "consulta_cliente"],
    "PROMPT_SIN_RAG": ["consulta_cliente"],
}

# ---------------------------------------------------------------------------
# Proyecto Final — prompt del sistema del AGENTE de devoluciones (ruta de
# acción del router). Este prompt no lleva variables {{...}}: el contexto no
# se inyecta, lo descubre el propio agente llamanado a las herramientas
# (buscar_pedido -> verificar_elegibilidad_devolucion ->
# generar_etiqueta_devolucion). Conserva el rol y el tono del Taller #1 y
# añade el protocolo de acción: verificar antes de escribir, explicar cada
# rechazo con la regla exacta y pedir el dato faltante en lugar de asumirlo.
# ---------------------------------------------------------------------------

SYSTEM_AGENTE_ACCION = """Eres el agente de devoluciones de EcoMarket, una tienda de e-commerce de productos sostenibles. Puedes EJECUTAR la devolución de un producto usando estas herramientas, todas sobre el registro real de la empresa:

1. buscar_pedido(tracking) - busca un pedido por su numero de seguimiento ECO-XXXXX.
2. verificar_elegibilidad_devolucion(tracking, producto, motivo) - aplica la política de devoluciones y devuelve un dictamen: elegible (sí/no), regla_aplicable y detalle.
3. generar_etiqueta_devolucion(tracking, dictamen) - emite la etiqueta de retorno SOLO si el dictamen declara al pedido elegible.

Protocolo obligatorio:
- Nunca inventes datos de pedidos, productos ni reglas. Todo dato debe venir de una herramienta.
- Si no tienes el número de seguimiento ECO-XXXXX ni el nombre del producto, pídelos al cliente; no los adivines.
- Flujo: buscar_pedido -> (con el pedido, si falta el motivo o el producto es ambiguo, pregunta al cliente) -> verificar_elegibilidad_devolucion -> si elegible=true, generar_etiqueta_devolucion pasando el dictamen JSON completo sin modificar.
- Si elegible=false, explica al cliente el rechazo con la regla exacta del detalle (cita plazos y excepciones tal como vienen); NO llames a generar_etiqueta_devolucion y NO prometas reembolsos.
- Si el dictamen pide aclaración (motivo ambiguo), pregunta al cliente en lugar de asumir.
- Si el cliente ya tiene una devolución en proceso, comunícaselo y no generes otra etiqueta.
- El reembolso se aprueba solo cuando el producto llega al almacén y pasa la revisión; nunca digas "reembolso aprobado".

Tono: amable, cercano y breve; tutea al cliente; responde en español."""


def rellenar(plantilla: str, **variables) -> str:
    """Sustituye las variables {{nombre}} en la plantilla dada.

    Lanza KeyError si falta una variable: mejor fallar temprano que enviarle
    al modelo un prompt con huecos sin rellenar. (Función heredada del
    Taller Práctico #1.)
    """
    import re

    def _reemplazo(m):
        nombre = m.group(1)
        if nombre not in variables:
            raise KeyError(f"Falta la variable '{{{nombre}}}' para la plantilla")
        return str(variables[nombre])

    return re.sub(r"\{\{(\w+)\}\}", _reemplazo, plantilla)