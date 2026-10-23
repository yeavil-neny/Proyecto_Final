# -*- coding: utf-8 -*-
"""
Interfaz web del asistente de EcoMarket (Fase 4 del Proyecto Final).

Interfaz construida con Streamlit (eleccion justificada en
docs/fase4-despliegue.md). Reune en una sola conversacion las dos rutas de
la arquitectura router:

  - Ruta informativa: el RAG del Taller #2 responde con citas y, si nada
    supera el umbral, escala honestamente.
  - Ruta de accion: el agente de devoluciones ejecuta con las herramientas
    (buscar_pedido, verificar_elegibilidad_devolucion,
    generar_etiqueta_devolucion) y mantiene conversacion de varios turnos
    (si falta el tracking, el producto o el motivo, pregunta al cliente).

Para la demo funcional, el razonamiento queda visible: la decision del
router como pie de firma y las llamadas de herramienta con su JSON dentro
de un expander (tambien las fuentes del RAG con su distancia coseno).

Uso (desde la raiz del repositorio, con GEMINI_API_KEY en .env):

  streamlit run src/app_devoluciones.py

Es una simulacion educativa: las herramientas operan sobre los archivos de
data/ del Taller #2 y la interface lo aclara en el margen.
"""

import io
import json
import os
import sys
from contextlib import redirect_stdout

import streamlit as st

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

import agente
import herramientas
import rag_ecomarket

# ---------------------------------------------------------------------------
# Inicializacion (una vez por proceso: el agente y la base se comparten
# entre recargas de la pagina; la conversacion vive en st.session_state)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Cargando el asistente: embeddings, base vectorial, agente...")
def iniciar():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(RAIZ, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY: copiala en un archivo .env en la raiz del repositorio (ver .env.example)."
        )
    llm = rag_ecomarket.llamar_llm(api_key)
    llm_agente = agente.llamar_llm_agente(api_key)
    vectorstore = rag_ecomarket.construir_base_conocimiento()
    ejecutor = agente.construir_agente(llm_agente, herramientas.HERRAMIENTAS)
    return {"llm": llm, "vectorstore": vectorstore, "ejecutor": ejecutor}


# ---------------------------------------------------------------------------
# Turnos
# ---------------------------------------------------------------------------

def turno_agente(consulta, historial_agente):
    """Ejecuta un turno de la ruta de accion con el historial de la conversacion."""
    return agente._herramientas_ejecutadas(iniciar()["ejecutor"], consulta, historial_agente)


def turno_informativo(consulta):
    """Ejecuta un turno del RAG del Taller #2 y recoge las fuentes impresionadas."""
    sistema = iniciar()
    pantalla = io.StringIO()
    with redirect_stdout(pantalla):
        texto = rag_ecomarket.responder(consulta, sistema["vectorstore"], sistema["llm"])
    return texto, pantalla.getvalue()


# ---------------------------------------------------------------------------
# Presentacion
# ---------------------------------------------------------------------------

def mostrar_respuesta(mensaje):
    with st.chat_message("assistant", avatar="🌿"):
        st.caption("Ruta informativa (RAG): " + mensaje["razon"] if mensaje["ruta"] == "informativa"
                   else "Ruta de acción (agente): " + mensaje["razon"])
        if mensaje.get("detalle_de_ruta"):
            with st.expander("Detalle de la ruta"):
                st.code(mensaje["detalle_de_ruta"], language=None)
        if mensaje.get("trazas"):
            herramienta_llamadas = ", ".join(paso["herramienta"] for paso in mensaje["trazas"])
            with st.expander(f"Razonamiento del agente: {len(mensaje['trazas'])} llamada(s) ({herramienta_llamadas})"):
                for paso in mensaje["trazas"]:
                    st.markdown(f"**{paso['herramienta']}**")
                    st.caption("Argumentos")
                    st.code(json.dumps(paso["argumentos"], ensure_ascii=False), language="json")
                    st.caption("Salida de la herramienta")
                    try:
                        st.code(json.dumps(json.loads(paso["salida"]), ensure_ascii=False, indent=2), language="json")
                    except (json.JSONDecodeError, TypeError):
                        st.code(str(paso["salida"]), language=None)
        st.markdown(mensaje["texto"])


# ---------------------------------------------------------------------------
# Pagina
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Asistente EcoMarket", page_icon="🌿", layout="centered")

st.title("Asistente de EcoMarket 🌿")
st.caption(
    "Agente de devoluciones + asistente informativo (arquitectura router). "
    "Simulación educativa sobre los datos del Taller #2: las herramientas operan sobre "
    "data/ y ninguna interacción alcanza un sistema real."
)

with st.sidebar:
    st.header("Cómo funciona")
    st.markdown(
        "- Una **pregunta** va al RAG del Taller #2 (respuestas con citas; si nada "
        "supera el umbral, escala honestamente).\n"
        "- Una **orden de devolución** va al agente: busca el pedido, verifica la "
        "elegibilidad con la política real y genera la etiqueta si corresponde.\n"
        "- Si falta el número de seguimiento, el producto o el motivo, el agente "
        "**pregunta** en lugar de asumir."
    )
    st.header("Consultas de ejemplo")
    ejemplos = [
        "Quiero devolver los envases de vidrio del ECO-10005, ya no los necesito",
        "Quiero devolver los envases de vidrio del ECO-10005",
        "¿Cuál es el estado del pedido ECO-10003?",
        "¿Qué productos no se pueden devolver?",
        "Me llegó dañada la máquina de afeitar, quiero devolverla",
        "Quiero devolver el café del ECO-10006, no me gustó",
    ]
    for ejemplo in ejemplos:
        if st.button(ejemplo, use_container_width=True):
            st.session_state["cola_consulta"] = ejemplo
            st.rerun()
    if st.button("Reiniciar conversación", use_container_width=True):
        st.session_state.pop("mensajes", None)
        st.session_state.pop("historial_agente", None)
        st.rerun()

if "mensajes" not in st.session_state:
    st.session_state["mensajes"] = []
if "historial_agente" not in st.session_state:
    st.session_state["historial_agente"] = []

for mensaje in st.session_state["mensajes"]:
    if mensaje["autor"] == "usuario":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(mensaje["texto"])
    else:
        mostrar_respuesta(mensaje)

consulta = st.chat_input("Escribe tu consulta: por ejemplo, el estado de tu pedido o una devolución")
if "cola_consulta" in st.session_state:
    consulta = st.session_state.pop("cola_consulta")

if consulta:
    st.session_state["mensajes"].append({"autor": "usuario", "texto": consulta})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(consulta)

    try:
        ruta, razon = agente.enrutar(consulta)
        nuevo_mensaje = {"autor": "asistente", "ruta": ruta, "razon": razon}
        if ruta == "accion":
            respuesta, trazas, mensajes_completos = turno_agente(
                consulta, st.session_state["historial_agente"]
            )
            st.session_state["historial_agente"] = mensajes_completos
            nuevo_mensaje |= {"texto": respuesta, "trazas": trazas}
        else:
            texto, detalle = turno_informativo(consulta)
            nuevo_mensaje |= {"texto": texto, "detalle_de_ruta": detalle or None}
        st.session_state["mensajes"].append(nuevo_mensaje)
        st.rerun()
    except Exception as error:
        st.error(
            f"No se pudo completar el turno: {error}\n\n"
            "Si fue un error temporal de red, de la API o de cuota diaria "
            "(el nivel gratuito de Gemini impone 20 peticiones por día), reintenta más tarde."
        )