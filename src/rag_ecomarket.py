# -*- coding: utf-8 -*-
"""
Sistema RAG del asistente de atención al cliente de EcoMarket.

Taller Práctico #2 — caso EcoMarket (continuación del Taller Práctico #1).

El asistente del Taller #1 atendía solo dos flujos predefinidos (estado de
pedido y devolución) inyectando directamente el JSON del pedido o la política
como contexto (mini-RAG didáctico). Este script generaliza la solución con un
RAG real: el contexto se RECUPERA por similitud semántica de una base de
conocimiento indexada, y si la recuperación no produce material pertinente,
el asistente lo comunica con honestidad y ofrece escalar a un asesor humano
(comportamiento exigido por el enunciado del taller).

Pipeline (Fases 1 y 2 del taller):

  1. Carga de la base de conocimiento: 4 tipos de documentos en data/
     (política de devoluciones en Markdown, pedidos en JSON, inventario en
     CSV y preguntas frecuentes en JSON).
  2. Segmentación por tipo de documento (chunks semánticamente autónomos).
  3. Indexación: embeddings open-source (Sentence-Transformers multilingüe)
     y base vectorial ChromaDB persistente, con similitud coseno.
  4. Consulta: recuperación top-k con distancias -> umbral de pertinencia ->
     plantilla de prompt (Rol -> Contexto -> Instrucciones -> Restricciones,
     misma del Taller #1) -> LLM (Gemini, capa gratuita, endpoint compatible
     con OpenAI).

Uso (desde la raíz del repositorio):

  python src/rag_ecomarket.py                     # bucle de chat interactivo
  python src/rag_ecomarket.py --pregunta "¿..."   # una consulta, un turno
  python src/rag_ecomarket.py --pregunta "¿..." --sin-rag
                                                  # modo control del experimento
                                                  # (sin contexto recuperado)
  python src/rag_ecomarket.py --umbral 0.55 --k 4 # calibración manual

Requiere la variable GEMINI_API_KEY en un archivo .env en la raíz del repositorio
(ver .env.example). Ver notebook notebooks/Taller2_RAG_EcoMarket.ipynb para la
ejecución documentada en Colab con los casos de prueba.
"""

import argparse
import csv
import json
import os
import re
import sys

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Rutas y constantes de arquitectura (Fase 1)
# ---------------------------------------------------------------------------

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_DATOS = os.path.join(RAIZ, "data")
RUTA_CHROMA = os.path.join(RAIZ, "chroma_ecomarket")

# Modelo de embeddings elegido en la Fase 1: open-source de Hugging Face,
# multilingüe (español incluido), vectores de 384 dimensiones, corre sin
# GPU. Su límite de entrada (128 tokens) determinó la segmentación de la
# Fase 2: los chunks están calibrados para caber completos (verificado
# token a token en el notebook).
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Modelo LLM del Taller #1, vía endpoint de Gemini compatible con OpenAI.
BASE_URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODELO_LLM = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Umbral de pertinencia sobre la distancia coseno que devuelve Chroma
# (0 = idénticos, mayor = menos similares; una distancia de UMBRAL equivale
# a una similitud coseno de 1 - UMBRAL). Se calibró con los casos de prueba
# del notebook: consultas dentro del dominio del corpus obtienen distancias
# claramente menores que consultas fuera de dominio. Si se recalibra, se
# puede ajustar aquí o con --umbral.
UMBRAL_DISTANCIA = 0.55

# Cantidad de chunks que entra al bloque de contexto del prompt.
K_CHUNKS = 4

# Detecta un número de seguimiento EcoMarket (ECO-XXXXX) dentro de la
# consulta: si el cliente pregunta por pedido específico, la recuperación se
# filtra a los documentos de tipo "pedido" (enrutamiento simple de la
# herramienta de recuperación).
PATRON_TRACKING = re.compile(r"ECO-\d{5}")

# Techo de segmentación: un chunk mide como máximo estos caracteres de
# contenido. Se fijó MEDIENDO el tokenizador del modelo de embeddings: el
# corpus completo queda bajo los 128 tokens del modelo sin truncarse
# (verificación celda a celda en el notebook).
TAMANO_CHUNK = 400
OVERLAP_CHUNK = 60      # solapamiento para pasajes transversales


# ---------------------------------------------------------------------------
# Carga y segmentación de cada tipo de documento (Fase 2)
# ---------------------------------------------------------------------------
# Decisiones: los documentos estructurados (pedidos, inventario, FAQ) se
# segmentan por registro natural (un pedido, un SKU, una FAQ por chunk),
# porque ese registro es el átomo que el cliente consulta y nunca se debe
# mezclar con otro. La política (texto narrativo por secciones Markdown) usa
# un splitter recursivo con separadores jerárquicos propios del Markdown.

def cargar_politica(ruta):
    """Carga la política de devoluciones dividida por secciones Markdown.

    Cada chunk es una sección completa; se usa RecursiveCharacterTextSplitter
    con separadores jerárquicos (sección, párrafo, oración) por si una
    sección superara el tamaño máximo, con overlap para no cortar reglas.
    """
    # Import perezoso dentro de la funcion: langchain/text_splitters es dependencia pesada
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document

    texto = open(ruta, encoding="utf-8").read()

    # La etiqueta compacta [Política EcoMarket | <sección>] va al inicio de
    # cada chunk para que el modelo sepa de dónde proviene cada dato sin
    # gastar caracteres del techo del tokenizador.
    cuerpo = texto.replace("# Política de Devoluciones de EcoMarket", "").strip()

    secciones = cuerpo.split("\n## ")
    documentos = []
    for seccion in secciones:
        seccion = seccion.strip()
        if not seccion:
            continue
        encabezado, seccion_limpia = (seccion.split("\n", 1) + [""])[:2]
        seccion_limpia = seccion_limpia.strip()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=TAMANO_CHUNK,
            chunk_overlap=OVERLAP_CHUNK,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        for fragmento in splitter.split_text(seccion_limpia):
            documentos.append(Document(
                page_content=f"[Política EcoMarket | {encabezado.strip('# ')}]\n{fragmento}",
                metadata={"tipo": "politica", "seccion": encabezado.strip("# ")},
            ))
    return documentos


def cargar_pedidos(ruta):
    """Carga el registro de pedidos: un chunk por pedido.

    Se serializa el objeto JSON completo del pedido (con los campos que el
    cliente consulta) e incluir el número de seguimiento al inicio del
    texto hace que la consulta "ECO-10003" sea semánticamente próxima a su
    propio registro. Un chunk por pedido evita mezclar estados o productos
    de pedidos distintos en el mismo fragmento.
    """
    from langchain_core.documents import Document

    datos = json.load(open(ruta, encoding="utf-8"))
    documentos = []
    for pedido in datos["pedidos"]:
        seguimiento = pedido["tracking_number"]
        # Los campos se ordenan por utilidad esperada en la respuesta y el
        # enlace de rastreo va al FINAL: si un chunk superara los 128 tokens
        # del modelo de embeddings, el truncamiento silencioso corta la cola,
        # y lo crítico (estado, fechas, motivo) ya está adelante.
        notas = pedido["notas"] or ""
        # La URL no entra al chunk: los enlaces consumen ~12 tokens cada uno
        # en el tokenizador y el enlace es determinista a partir del número
        # de seguimiento. Se conserva en metadata y la plantilla del prompt
        # pide construirla cuando la respuesta sea sobre un pedido.
        contenido = (
            f"[Pedido {seguimiento}] "
            f"Estado: {pedido['estado']}. "
            f"Productos: {', '.join(pedido['productos'])}. "
            f"Total: {pedido['total']}. "
            f"Fechas: pedido {pedido['fecha_pedido']}; est.: {pedido['fecha_estimada_entrega'] or 'sin fecha'}; "
            f"entrega: {pedido['fecha_entrega'] or 'no entregado'}. "
            + (f"Notas: {notas.rstrip('.')}. " if notas else "")
            + f"Transportadora: {pedido['transportadora']}."
        )
        documentos.append(Document(
            page_content=contenido,
            # El nombre del cliente va solo en metadata: no se vectoriza (ahorra
            # tokens del techo) y el texto indexado conserva menos datos personales.
            metadata={"tipo": "pedido", "tracking": seguimiento,
                      "cliente": pedido["cliente"],
                      "actualizado": pedido["ultima_actualizacion"]},
        ))
    return documentos


def cargar_inventario(ruta):
    """Carga el inventario de productos: un chunk por SKU (fila del CSV)."""
    from langchain_core.documents import Document

    documentos = []
    with open(ruta, encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            disponible = "disponible" if fila["disponibilidad"].strip().lower() == "true" else "temporalmente sin stock"
            notas = f" Notas: {fila['notas']}." if fila["notas"].strip() else ""
            precio_txt = f"{int(fila['precio_cop']):,}".replace(",", ".")  # 45000 -> 45.000 (formato COP)
            contenido = (
                f"[Producto {fila['sku']}] "
                f"{fila['producto']} (SKU {fila['sku']}), categoría {fila['categoria']}. "
                f"Precio: ${precio_txt} COP. "
                f"Stock: {fila['stock']} unidades, estado {disponible}.{notas}"
            )
            documentos.append(Document(
                page_content=contenido,
                metadata={"tipo": "inventario", "sku": fila["sku"]},
            ))
    return documentos


def cargar_faqs(ruta):
    """Carga las preguntas frecuentes: un chunk por par pregunta-respuesta.

    La pregunta y su respuesta permanecen juntas: la pregunta aporta la
    superficie semántica más parecida a la consulta real del usuario y el
    chunk recuperado llega al prompt con su respuesta dentro.
    """
    from langchain_core.documents import Document

    datos = json.load(open(ruta, encoding="utf-8"))
    documentos = []
    for faq in datos["faqs"]:
        contenido = (
            f"[FAQ {faq['id']} | {faq['categoria']}] "
            f"Pregunta: {faq['pregunta']}\nRespuesta: {faq['respuesta']}"
        )
        documentos.append(Document(
            page_content=contenido,
            metadata={"tipo": "faq", "id": faq["id"]},
        ))
    return documentos


def construir_base_conocimiento():
    """Carga, segmenta e indexa los documentos en la base vectorial.

    Devuelve el vectorstore Chroma (persistente, espacio coseno). El corpus
    es pequeño, así que se reconstruye desde cero en cada ejecución: menos
    de un segundo de cómputo y garantiza que el índice refleje siempre los
    archivos actuales de data/.
    """
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    import chromadb

    # Reindexación desde cero: el índice debe reflejar siempre los archivos
    # vigentes de data/ (el corpus se reconstruye en menos de un segundo).
    # Los documentos se borran de la colección SIN eliminar la carpeta: si este
    # mismo runtime ya había abierto la base (por ejemplo, al re-ejecutar el
    # notebook), eliminar el archivo SQLite por debajo de una conexión abierta
    # la deja inservible y la reinicialización falla con "(code: 14) unable to
    # open database file". Borrar la colección es lo que hace un sistema de
    # producción con un índice que se reconstruye: se desactiva, no se raspa.
    if os.path.isdir(RUTA_CHROMA):
        cliente_previo = chromadb.PersistentClient(path=RUTA_CHROMA)
        for coleccion in cliente_previo.list_collections() or []:
            cliente_previo.delete_collection(coleccion.name)

    documentos = []
    fuentes = {
        "politica": cargar_politica(os.path.join(RUTA_DATOS, "politicas_devolucion.md")),
        "pedido": cargar_pedidos(os.path.join(RUTA_DATOS, "pedidos.json")),
        "inventario": cargar_inventario(os.path.join(RUTA_DATOS, "inventario_productos.csv")),
        "faq": cargar_faqs(os.path.join(RUTA_DATOS, "faqs.json")),
    }
    for tipo, docs in fuentes.items():
        print(f"Indexando '{tipo}': {len(docs)} chunks")
        documentos.extend(docs)

    print(f"Calculando embeddings con {MODELO_EMBEDDINGS} ...")
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)

    # Espacio coseno: la distancia devuelta por la búsqueda es interpretable
    # (0 = textos idénticos en dirección) y de ella se deriva el umbral de
    # pertinencia que dispara el escalado honesto.
    vectorstore = Chroma.from_documents(
        documents=documentos,
        embedding=embeddings,
        persist_directory=RUTA_CHROMA,
        collection_metadata={"hnsw:space": "cosine"},
    )
    print(f"Base de conocimiento lista: {len(documentos)} chunks en ChromaDB.\n")
    return vectorstore


# ---------------------------------------------------------------------------
# Recuperación con verificación de pertinencia (el "reflection" del agente)
# ---------------------------------------------------------------------------

def recuperar(vectorstore, consulta, k=K_CHUNKS):
    """Busca los k chunks más similares y devuelve pares (documento, distancia).

    Si la consulta contiene un número de seguimiento ECO-XXXXX, la búsqueda
    se filtra a los documentos de tipo "pedido": es una consulta sobre un
    registro específico y los chunks de política o catálogo serían ruido.
    """
    if PATRON_TRACKING.search(consulta.upper()):
        return vectorstore.similarity_search_with_score(
            consulta, k=k, filter={"tipo": "pedido"}
        )
    return vectorstore.similarity_search_with_score(consulta, k=k)

def formatear_contexto(resultados):
    """Junta los chunks recuperados en el texto del bloque de contexto."""
    return "\n---\n".join(doc.page_content for doc, _ in resultados)

def hay_material_pertinente(resultados, umbral=UMBRAL_DISTANCIA):
    """Verifica si al menos un chunk superó el umbral de pertinencia.

    Es la verificación previa a la generación: si nada del corpus se parece
    lo suficiente a la consulta, el asistente responde con el mensaje
    determinista MENSAJE_SIN_HERRAMIENTAS sin llamar al LLM.
    """
    return min(d for _, d in resultados) <= umbral if resultados else False


# ---------------------------------------------------------------------------
# LLM y generación de la respuesta
# ---------------------------------------------------------------------------

def llamar_llm(api_key):
    """Construye el LLM del Taller #1 vía endpoint de Gemini compatible con OpenAI."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=MODELO_LLM,
        api_key=api_key,
        base_url=BASE_URL_GEMINI,
        temperature=0.1,  # baja variación: las citas del contexto deben ser fieles
    )

def generar_respuesta(llm, consulta, contexto):
    """Rellena la plantilla del Taller #1 con el contexto RAG y consulta al modelo."""
    import prompts as plantillas

    mensajes = [
        ("system", plantillas.SYSTEM_AGENTE_ECOMARKET_RAG),
        ("human", plantillas.rellenar(plantillas.PROMPT_RAG, contexto_rag=contexto, consulta_cliente=consulta)),
    ]
    return llm.invoke(mensajes).content

def responder(consulta, vectorstore, llm, umbral=UMBRAL_DISTANCIA, k=K_CHUNKS, mostrar_fuentes=True):
    """Ejecuta el flujo completo (con RAG) para una consulta y devuelve la respuesta.

    Pipeline: recuperar -> verificar umbral -> llenar plantilla -> LLM.
    Si nada supera el umbral, se devuelve la respuesta determinista de
    escalamiento (MENSAJE_SIN_HERRAMIENTAS) sin llamar al LLM.
    """
    import prompts as plantillas

    resultados = recuperar(vectorstore, consulta, k=k)
    if mostrar_fuentes and resultados:
        print("Fuentes recuperadas (distancia coseno, menor = más similar):")
        for doc, distancia in resultados:
            meta = doc.metadata
            identificador = meta.get("tracking") or meta.get("sku") or meta.get("seccion") or meta.get("id", "")
            print(f"  - {meta.get('tipo')} {identificador} (distancia={distancia:.3f})")

    if not hay_material_pertinente(resultados, umbral):
        print("  -> Ningún chunk superó el umbral de pertinencia; el asistente escala con honestidad.")
        return plantillas.MENSAJE_SIN_HERRAMIENTAS

    contexto = formatear_contexto(resultados)
    return generar_respuesta(llm, consulta, contexto)


# ---------------------------------------------------------------------------
# Modo control sin RAG (equivalente del flag --basico del Taller #1)
# ---------------------------------------------------------------------------

def responder_sin_rag(consulta, llm):
    """Envía la consulta al LLM sin contexto recuperado ni restricciones.

    El objetivo del experimento es mostrar qué inventa o no el modelo cuando
    responde con su conocimiento general sobre una empresa que no existe en
    su entrenamiento.
    """
    import prompts as plantillas

    return llm.invoke([
        ("human", plantillas.rellenar(plantillas.PROMPT_SIN_RAG, consulta_cliente=consulta))
    ]).content


# ---------------------------------------------------------------------------
# Interfaz de línea de comandos
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Asistente RAG de EcoMarket (Taller Práctico #2)")
    parser.add_argument("--pregunta", help="consulta puntual; si se omite, se abre el bucle de chat")
    parser.add_argument("--sin-rag", action="store_true", help="modo control: la consulta va al LLM sin contexto recuperado")
    parser.add_argument("--umbral", type=float, default=UMBRAL_DISTANCIA, help="umbral de distancia coseno para escalar (por defecto 0.55)")
    parser.add_argument("--k", type=int, default=K_CHUNKS, help="número de chunks recuperados (por defecto 4)")
    args = parser.parse_args()

    load_dotenv(os.path.join(RAIZ, ".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Falta GEMINI_API_KEY: cópiala en un archivo .env en la raíz del repositorio (ver .env.example).")
        sys.exit(1)

    llm = llamar_llm(api_key)

    if args.sin_rag:
        if args.pregunta is None:
            parser.error("--sin-rag requiere --pregunta: el modo control es de un solo turno")
        respuesta = responder_sin_rag(args.pregunta, llm)
        print("\nRespuesta del asistente (sin RAG):\n")
        print(respuesta)
        return

    vectorstore = construir_base_conocimiento()

    if args.pregunta is not None:
        respuesta = responder(args.pregunta, vectorstore, llm, umbral=args.umbral, k=args.k)
        print("\nRespuesta del asistente:\n")
        print(respuesta)
        return

    print("¡Asistente RAG de EcoMarket listo!\nEscribe una consulta y presiona Enter. Escribe 'salir' para terminar.\n")
    while True:
        consulta = input("\nTu consulta: ").strip()
        if consulta.lower() == "salir":
            break
        if not consulta:
            continue
        try:
            respuesta = responder(consulta, vectorstore, llm, umbral=args.umbral, k=args.k)
            print("\nRespuesta del asistente:\n")
            print(respuesta)
        except Exception as error:
            print(f"\nError al procesar la consulta: {error}\nSi fue un error temporal de red o de la API, reintenta la misma consulta.")


if __name__ == "__main__":
    main()