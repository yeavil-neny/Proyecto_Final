# -*- coding: utf-8 -*-
"""
Agente de devoluciones de EcoMarket (Fases 1 y 2 del Proyecto Final).

Arquitectura router (docs/propuesta-preliminar.md, 3.1): la consulta del
cliente entra por un ROUTER con reglas de entrada deterministas y se dirige a
una de dos rutas:

  Ruta informativa -> el sistema RAG del Taller #2, SIN CAMBIOS
                      (src/rag_ecomarket.py y src/prompts.py, copiados)
  Ruta de accion   -> el agente de devoluciones (LangChain 1.x,
                      create_agent) sobre las tres herramientas de
                      src/herramientas.py

El router es código, no un clasificador LLM: la decisión de enrutamiento es
barata, auditable y reproducible. La regla acordada (propuesta 3.1) separa:

  - PREGUNTA (informacion) -> RAG: consultas en forma de pregunta (signo de
    interrogacion o palabras interrogativas) o consultas sobre la politica
    (plazos, condiciones) NO tocan las herramientas.
  - ORDEN (accion) -> agente: enunciados en primera persona o imperativos
    que piden ejecutar la devolucion ("quiero devolver...", "me llego
    defectuoso...", "genera la etiqueta..."), con o sin numero de seguimiento.

Uso (desde la raiz del repositorio, requiere GEMINI_API_KEY en .env):

  python src/agente.py --consulta "quiero devolver la vela del pedido ECO-10007, llego defectuosa"
  python src/agente.py --consulta "Cuando llega mi pedido ECO-10003?"   # -> ruta informativa (RAG)
  python src/agente.py --chat                                          # bucle interactivo
  python src/agente.py --consulta "..." --razonamiento                 # muestra cada paso del agente
"""

import argparse
import datetime
import json
import os
import re
import sys

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

import herramientas
import prompts as plantillas
import rag_ecomarket


RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# ROUTER: reglas de entrada deterministas (Fase 1, decision 3.1 de la propuesta)
# ---------------------------------------------------------------------------

# Palabras interrogativas/consultivas: su presencia sugiere una PREGUNTA
# (informacion) y no una ORDEN de ejecucion. La politica, sus plazos y las
# condiciones se consultan con estas formas.
PATRONES_PREGUNTA = (
    r"como\s+(solicito|funciona|hago|solicitar|puedo|devuelvo)",
    r"cuando\s+(llega|es|puedo|me)", r"cuantos?\s+dias", r"cuales?\s+(son|es|el)",
    r"que\s+(puedo|productos|regla)", r"donde\b.*\b(devolver|entregar|punto)",
    r"puedo\s+devolver", r"se\s+puede\s+devolver", r"plazo\b", r"politica\b.*devolucion",
)

# ORDENES de accion: enunciados en primera persona o imperativos que piden
# EJECUTAR la devolucion. No requieren el numero de seguimiento: si falta, el
# agente lo pide (la herramienta buscar_pedido falla con formato_invalido y
# el protocolo del agente lo transforma en una pregunta al cliente).
PATRONES_ORDEN = (
    r"\b(quiero|deseo|necesito|voy\s+a|me\s+arrepiento)\b.*\b(devolver|devoluc|reembols)",
    r"\bdevolver\b|\bdevuelv[ei]\w*\b|\bdevolv(e|eme)[a]?\b",
    r"\b(haz|realiza|procesa|emite|genera|solicita)\b.*\b(devolu|etiqueta|guia|reembolso)",
    r"\b(llega|me\s+llego|me\s+llego|vino)\b.*\b(defectuoso|defect|dañado|danado|roto|incorrecto|incorrect)",
    r"\b(defectuoso|roto|dañado|danado)\b.*\b(devolver|devoluc|etiqueta)",
    r"\b(etiqueta|guia)\s+de\s+(devolucion|retorno)",
)


def _coincide(consulta, patrones):
    texto = consulta.lower().strip()
    return re.search("|".join(patrones), texto) is not None


def enrutar(consulta):
    """Decide la ruta para una consulta y devuelve (ruta, razon).

    Orden de evaluacion de las reglas (de menos a mas ambiguo):
      1. Orden de accion sin rasgos de pregunta -> agente.
      2. Forma de pregunta (signo o palabras interrogativas + patron) -> RAG.
      3. 'devoluc..' sin rasgo claro se queda en RAG: la ruta accion solo se
         toma con el consenso de una orden; una duda no deberia poder
         escribir datos (principio de seguridad de la propuesta 3.1).
    """
    es_orden = _coincide(consulta, PATRONES_ORDEN)
    forma_pregunta = "?" in consulta or _coincide(consulta, PATRONES_PREGUNTA)

    if es_orden and not forma_pregunta:
        return "accion", "consenso de orden de devolucion sin forma de pregunta"
    if forma_pregunta:
        return "informativa", "forma de pregunta o consulta sobre la politica"
    if es_orden:
        return "accion", "orden de devolucion mezclada con forma interrogativa"
    return "informativa", "sin orden de ejecucion detectada; por defecto no toca las herramientas"


# ---------------------------------------------------------------------------
# AGENTE de la ruta de accion (LangChain, create_tool_calling_agent)
# ---------------------------------------------------------------------------

# --- Transporte OpenAI-compatible de Gemini con round-trip de firmas de
# pensamiento ---
#
# Los modelos Gemini de la serie 3 exigen reenviar, en cada vuelta del bucle
# de herramientas, la firma de pensamiento (thought_signature) que ellos
# mismos entregan junto a cada function_call
# (https://ai.google.dev/gemini-api/docs/thought-signatures). El cliente HTTP
# de langchain-openai reconstruye el historial desde los mensajes parseados y
# descarta ese campo, y la API responde 400
# "Function call is missing a thought_signature". Se resuelve con un proxy
# del cliente HTTP: cosecha la firma de cada respuesta y la repone en la
# peticion siguiente, antes de que viaje.

class _ClienteConFirmas:
    """Proxy del cliente de chat.completions que repone y cosecha firmas."""

    def __init__(self, cliente, firmas):
        self._cliente = cliente
        self._firmas = firmas
        # langchain-openai llama self.client.with_raw_response.create(...):
        # el proxy expone esa misma superficie.
        self.with_raw_response = self

    def create(self, **payload):
        for mensaje in payload.get("messages") or []:
            if mensaje.get("role") != "assistant":
                continue
            for llamada in mensaje.get("tool_calls") or []:
                firma = self._firmas.get(llamada.get("id"))
                if firma:
                    llamada.setdefault("extra_content", {})["google"] = {
                        "thought_signature": firma
                    }
        respuesta = self._cliente.with_raw_response.create(**payload)
        try:
            mensaje = respuesta.parse().choices[0].message
            for llamada in getattr(mensaje, "tool_calls", None) or []:
                extra = getattr(llamada, "extra_content", None) or (llamada.model_extra or {}).get("extra_content")
                firma = (extra or {}).get("google", {}).get("thought_signature")
                if firma and llamada.id:
                    self._firmas[llamada.id] = firma
        except Exception:  # la cosecha nunca debe romper el turno del agente
            pass
        return respuesta


class ChatGeminiConFirmas(ChatOpenAI):
    """ChatOpenAI que hace el round-trip de las firmas de pensamiento de Gemini.

    El resto del comportamiento es identico al LLM del Taller #2: mismo
    endpoint OpenAI-compatible de Gemini, mismas dependencias.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._firmas = {}
        self._cliente_original = self.client
        self.client = _ClienteConFirmas(self._cliente_original, self._firmas)


def llamar_llm_agente(api_key):
    """LLM del agente: el mismo modelo del Taller #2, con round-trip de firmas."""
    return ChatGeminiConFirmas(
        model=rag_ecomarket.MODELO_LLM,
        api_key=api_key,
        base_url=rag_ecomarket.BASE_URL_GEMINI,
        temperature=0.1,  # baja variacion: los dictamenes deben ser fieles
    )

def construir_agente(llm, herramientas_agente):
    """Construye el agente de LangChain 1.x (create_agent) con las herramientas del modulo herramientas.

    Nota de version: la propuesta preliminar mencionaba
    create_tool_calling_agent/AgentExecutor, el par de LangChain 0.x. El
    entorno en que ejecuta el proyecto tiene LangChain 1.x, que reemplazo ese
    par por el constructor create_agent (mismo ciclo de decision: el modelo
    elige herramienta y argumentos, el runtime ejecuta y alimenta al modelo
    hasta que produce la respuesta final); ahi quedo documentada la
    equivalencia en docs/fase2-implementacion.md.
    """
    from langchain.agents import create_agent

    return create_agent(llm, herramientas_agente, system_prompt=plantillas.SYSTEM_AGENTE_ACCION)


def _herramientas_ejecutadas(agente, entrada):
    """Ejecuta el agente y devuelve (respuesta, traza de pasos para observabilidad).

    En LangChain 1.x la traza de intermedios se reconstruye desde los
    mensajes del estado: cada AIMessage lleva las tool_calls que pidio y el
    ToolMessage siguiente lleva la salida JSON de la herramienta.
    """
    resultado = agente.invoke({"messages": [{"role": "user", "content": entrada}]})
    mensajes = resultado["messages"]
    trazas = []
    for mensaje in mensajes:
        for llamada in getattr(mensaje, "tool_calls", None) or []:
            trazas.append({
                "herramienta": llamada["name"],
                "argumentos": llamada["args"],
                "salida": None,
            })
        if trazas and trazas[-1]["salida"] is None and getattr(mensaje, "type", "") == "tool":
            trazas[-1]["salida"] = mensaje.content
    respuesta = mensajes[-1].content
    return respuesta, trazas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _mostrar_trazas(trazas):
    for paso in trazas:
        print(f"  [herramienta] {paso['herramienta']}({paso['argumentos']})")
        try:
            salida = json.loads(paso["salida"])
            print(f"      -> {json.dumps(salida, ensure_ascii=False, indent=2)[:1200]}")
        except (json.JSONDecodeError, TypeError):
            print(f"      -> {paso['salida'][:300]}")


# ---------------------------------------------------------------------------
# Observabilidad (Fase 3): registro de turnos en JSONL (una linea por turno)
# data/registro_turnos.jsonl alimenta los KPIs del documento de analisis; es
# un registro de simulacion educativa y va excluido del repositorio.
# ---------------------------------------------------------------------------

RUTA_REGISTRO_TURNOS = os.path.join(RAIZ, "data", "registro_turnos.jsonl")


def registrar_turno(consulta, ruta, trazas, respuesta, duracion):
    """Persiste un turno completo (ruta, herramientas, respuesta, duracion).

    Si la escritura falla (p.ej. permisos), el turno del cliente no se ve
    afectado: la observabilidad se degrada, no detiene el servicio.
    """
    try:
        evento = {
            "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
            "ruta": ruta,
            "consulta": consulta,
            "herramientas": trazas,
            "respuesta": respuesta,
            "duracion_segundos": round(duracion, 2),
        }
        with open(RUTA_REGISTRO_TURNOS, "a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
    except OSError:
        pass


def ejecutar_turno(consulta, llm, ejecutor, vectorstore, mostrar_trazas=True):
    """Un turno completo pasando por el router. Imprime la ruta elegida y responde."""
    inicio = datetime.datetime.now()
    ruta, razon = enrutar(consulta)
    print(f"(router -> ruta {ruta}: {razon})")

    if ruta == "accion":
        respuesta, trazas = _herramientas_ejecutadas(ejecutor, consulta)
        if mostrar_trazas:
            _mostrar_trazas(trazas)
    else:
        respuesta = rag_ecomarket.responder(consulta, vectorstore, llm)
        trazas = []

    registrar_turno(consulta, ruta, trazas, respuesta, (datetime.datetime.now() - inicio).total_seconds())
    return respuesta


def main():
    parser = argparse.ArgumentParser(description="Agente de devoluciones de EcoMarket (Proyecto Final)")
    parser.add_argument("--consulta", help="consulta puntual; si se omite, se abre el bucle interactivo")
    parser.add_argument("--chat", action="store_true", help="bucle de chat interactivo")
    parser.add_argument("--razonamiento", action="store_true", help="mostrar cada llamada de herramienta y su salida")
    args = parser.parse_args()

    load_dotenv(os.path.join(RAIZ, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Falta GEMINI_API_KEY: copiala en un archivo .env en la raiz (ver .env.example).")
        sys.exit(1)

    print("Construyendo el agente: LLM + herramientas de devolucion ...")
    llm = rag_ecomarket.llamar_llm(api_key)
    llm_agente = llamar_llm_agente(api_key)
    if not args.chat and args.consulta is None:
        parser.error("pasa --consulta o usa --chat")

    # La ruta informativa necesita la base vectorial; la de accion, el agente.
    vectorstore = rag_ecomarket.construir_base_conocimiento()
    ejecutor = construir_agente(llm_agente, herramientas.HERRAMIENTAS)

    if args.consulta is not None:
        respuesta = ejecutar_turno(args.consulta, llm, ejecutor, vectorstore, args.razonamiento)
        print("\nRespuesta:\n")
        print(respuesta)
        return

    print("Agente de EcoMarket listo. Escribe 'salir' para terminar.\n")
    while True:
        consulta = input("\nTu consulta: ").strip()
        if consulta.lower() == "salir":
            break
        if not consulta:
            continue
        try:
            respuesta = ejecutar_turno(consulta, llm, ejecutor, vectorstore, args.razonamiento)
            print("\nRespuesta:\n")
            print(respuesta)
        except Exception as error:
            print(f"\nError al procesar la consulta: {error}\nSi fue un error temporal de red o de la API, reintenta.")


if __name__ == "__main__":
    main()