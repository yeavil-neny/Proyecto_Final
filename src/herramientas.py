# -*- coding: utf-8 -*-
"""
Herramientas del agente de devoluciones de EcoMarket (Fase 2 del Proyecto Final).

Son las herramientas que el enunciado exige como funciones (minimo dos sin
contar el RAG); este modulo define tres y el agente de agente.py las usa por
su nombre. Cada herramienta cumple un CONTRATO documentado (ver
docs/fase2-implementacion.md):

  1. buscar_pedido(tracking)
       -> Devuelve el pedido completo (productos, estado, fechas) o un error
          explicito (formato_invalido / pedido_no_encontrado).
  2. verificar_elegibilidad_devolucion(tracking, producto, motivo)
       -> Aplica las reglas de la politica de EcoMarket sobre los datos del
          pedido y del inventario y devuelve un dictamen estructurado.
  3. generar_etiqueta_devolucion(tracking, dictamen)
       -> Emite la etiqueta de retorno SOLO si el dictamen recibido declara al
          pedido elegible y la verificacion interna coincide; persiste el
          registro en data/etiquetas_emitidas.json (auditable, Fase 3).

Decisiones de diseno importantes (tambien documentadas en docs/fase2-implementacion.md):

- Todo es SIMULADO sobre los archivos de data/ del Taller #2 (pedidos.json,
  inventario_productos.csv, politicas_devolucion.md): no hay backend real.
  La persistencia de etiquetas es un JSON de registro, no una transaccion.
- RELOJ SIMULADO: el corpus esta fijado a la fecha_base de pedidos.json
  (2026-09-17). Si las herramientas usaran la fecha real del sistema, Todos
  los plazos del corpus estarian vencidos y ninguna demo funcionaria. El
  "hoy" del sistema puede sobreescribirse con la variable RELOJ_SIMULADO.
- Toda salida es JSON estructurado: el agente decide el siguiente paso con
  datos, no con prosa, y cada llamada queda registrable (Fase 3).
- La interpretacion del motivo es determinista (palabras clave), no LLM: la
  decision de negocio debe ser reproducible y auditable. Si el motivo no se
  puede clasificar, el dictamen lo declara (requiere_aclaracion) y el AGENTE
  pregunta al cliente en lugar de asumir.

Las funciones "_core" retornan diccionarios y no dependen de LangChain; las
versiones empaquetadas como @tool (para el agente) envuelven esas funciones
y serializan la salida a JSON. Las pruebas de pruebas_fase2.py evaluan las
funciones _core y el router sin llamar al LLM.
"""

import csv
import datetime
import json
import os
import re
import unicodedata

from langchain_core.tools import tool

# ---------------------------------------------------------------------------
# Rutas y constantes
# ---------------------------------------------------------------------------

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_DATOS = os.path.join(RAIZ, "data")
RUTA_PEDIDOS = os.path.join(RUTA_DATOS, "pedidos.json")
RUTA_INVENTARIO = os.path.join(RUTA_DATOS, "inventario_productos.csv")
RUTA_ETIQUETAS = os.path.join(RUTA_DATOS, "etiquetas_emitidas.json")

# Reglas de la politica (data/politicas_devolucion.md) que el motor usa:
# se citan por su seccion en los dictamenes para que cada rechazo explique
# la regla exacta (requisito del proceso de devolucion, punto 5 de la misma).
PLAZO_DIAS_GENERAL = 30          # "Condiciones generales": 30 dias calendario
PLAZO_DIAS_DEFECTO = 7           # "Excepciones": defecto/dano/incorrecto

# Detecta un numero de seguimiento EcoMarket (ECO-XXXXX); mismo patron del
# sistema RAG del Taller #2 (src/rag_ecomarket.py).
PATRON_TRACKING = re.compile(r"ECO-\d{5}")

# Direccion simulada de recepcion de devoluciones de EcoMarket.
DIRECCION_DEVOLUCIONES = "Bodega 7, Parque Industrial Sabana Norte, Bogota"


# ---------------------------------------------------------------------------
# Utilidades de normalizacion (búsqueda de productos por nombre)
# ---------------------------------------------------------------------------

def _texto_normalizado(texto):
    """Minúsculas, sin tildes ni puntuacion, con espacios colapsados.

    Sirve para comparar el nombre que menciona el cliente con los nombres
    de los productos del pedido y del inventario sin depender de tildes,
    mayusculas o parentesis.
    """
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def _frases_coinciden(consulta, nombre_producto):
    """True si todos los terminos de la consulta estan en el nombre del producto.

    Coincidencia por tokens y no por subcadena: 'vela aromatica' debe
    encontrar 'Vela de soya aromatica (frasco de vidrio)' aunque las palabras
    no esten contiguas en el nombre completo.
    """
    tokens_consulta = _texto_normalizado(consulta).split()
    tokens_producto = set(_texto_normalizado(nombre_producto).split())
    return bool(tokens_consulta) and set(tokens_consulta) <= tokens_producto


# ---------------------------------------------------------------------------
# Reglas de la politica (el motor de elegibilidad)
# ---------------------------------------------------------------------------

# Categorias del inventario que caen en la seccion "Productos que NO se
# pueden devolver" de la politica. La lista de exclusion es taxativa, asi
# que las categorias que no aparecen aqui (Hogar, Accesorios, Limpieza) son
# devolvibles.
CATEGORIAS_NO_DEVOLUBLES = {
    # Alimentos y bebidas (seccion 1): cafe, snacks, mieles, etc.
    "Despensa": "alimentos y bebidas",
    # Productos de higiene y cuidado personal (seccion 2): jabones, shampoo,
    # balsamos, cremas, cepillos de dientes, desodorantes.
    "Higiene solida": "higiene y cuidado personal",
    "Higiene sostenible": "higiene y cuidado personal",
    # Semillas y plantas (seccion 3): se detecta tambien por nombre abajo.
    "Semillas": "semillas y plantas",
}

# Terminos en el NOMBRE del producto que caen en la seccion 3 (semillas,
# plantas, kits de cultivo): el inventario marca algunos con la categoria
# "Despensa" pero su nota aclara la exclusion.
TERMINOS_NO_DEVOLUBLES_POR_NOMBRE = ("semilla", "planta viva", "kit de cultivo", "venta final")


def _regla_no_devoluble(nombre_producto, categoria):
    """Devuelve la razon de exclusion de la politica o None si es devolvible."""
    razon = CATEGORIAS_NO_DEVOLUBLES.get(categoria)
    nombre = _texto_normalizado(nombre_producto)
    for termino in TERMINOS_NO_DEVOLUBLES_POR_NOMBRE:
        if termino in nombre:
            return f"nombre del producto contiene '{termino}' (seccion 'Productos que NO se pueden devolver')"
    if razon:
        return f"categoria '{categoria}': {razon} (seccion 'Productos que NO se pueden devolver')"
    return None


# Clasificacion determinista del motivo (texto libre del cliente). El motor
# NUNCA asume: si ninguna huella aparece, el dictamen pide aclaracion al
# cliente via el agente.
MOTIVO_DEFECTO = ("defectuoso", "defecto", "danado", "dañado", "roto", "rota",
                  "partido", "partida", "mojado", "mojada", "fallo", "falla",
                  "incorrecto", "incorrecta", "diferente", "mal estado",
                  "no funciona", "no funciono", "vencido")
MOTIVO_CAMBIO_OPINION = ("cambio de opinion", "no me gusto", "no gustó",
                         "me arrepiento", "arrepentido", "arrepentida",
                         "ya no lo", "ya no la", "mejor no", "no lo quiero",
                         "no la quiero", "no lo necesito", "no la necesito",
                         "equivoque de", "equivoqué de", "queria otro",
                         "quería otro", "mas grande", "más grande",
                         "mas pequeno", "más pequeño")


def _clasificar_motivo(motivo):
    """Clasifica el motivo del cliente: defecto, cambio_opinion o ambiguo.

    'ambiguo' cubre tanto el motivo vacio como el que ninguna huella marca:
    la regla acordada es NO asumir (propuesta 3.2, manejo de errores): si el
    motivo no se clasifica con certeza, el dictamen pide aclaracion y el
    agente pregunta al cliente antes de continuar.
    """
    if not motivo or not motivo.strip():
        return "ambiguo"
    texto = _texto_normalizado(motivo)
    if any(_texto_normalizado(huella) in texto for huella in MOTIVO_DEFECTO):
        return "defecto"
    if any(_texto_normalizado(huella) in texto for huella in MOTIVO_CAMBIO_OPINION):
        return "cambio_opinion"
    return "ambiguo"


# ---------------------------------------------------------------------------
# Carga de datos de simulacion
# ---------------------------------------------------------------------------

def _cargar_pedidos():
    with open(RUTA_PEDIDOS, encoding="utf-8") as archivo:
        return {pedido["tracking_number"]: pedido
                for pedido in json.load(archivo)["pedidos"]}


def _cargar_inventario():
    with open(RUTA_INVENTARIO, encoding="utf-8") as archivo:
        return {fila["producto"]: fila for fila in csv.DictReader(archivo)}


def hoy():
    """Fecha 'hoy' del reloj simulado del sistema.

    Por defecto usa la fecha_base del corpus (data/pedidos.json, 2026-09-17)
    para que los plazos de la politica sean coherentes con los datos; puede
    sobreescribirse con la variable de entorno RELOJ_SIMULADO (AAAA-MM-DD).
    """
    override = os.getenv("RELOJ_SIMULADO", "").strip()
    if override:
        return datetime.date.fromisoformat(override)
    datos = json.load(open(RUTA_PEDIDOS, encoding="utf-8"))
    return datetime.date.fromisoformat(datos["fecha_base"])


# ---------------------------------------------------------------------------
# Herramienta 1: buscar pedido
# ---------------------------------------------------------------------------

def buscar_pedido_core(tracking):
    """Busca un pedido por numero de seguimiento. Ver contrato en el docstring de buscar_pedido."""
    registros = _cargar_pedidos()
    tracking = (tracking or "").strip().upper()

    if not re.fullmatch(PATRON_TRACKING.pattern, tracking):
        registro = PATRON_TRACKING.search(tracking)
        if registro:
            # El cliente pego texto alrededor (p.ej. "pedido ECO-10005"):
            # se rescata el patron en lugar de rechazar la consulta.
            tracking = registro.group(0)
        else:
            return {
                "exito": False,
                "error": "formato_invalido",
                "mensaje": ("El numero de seguimiento de EcoMarket tiene el formato ECO-XXXXX "
                            "(por ejemplo ECO-10005). Pidelo al cliente en lugar de adivinarlo."),
            }

    pedido = registros.get(tracking)
    if pedido is None:
        return {
            "exito": False,
            "error": "pedido_no_encontrado",
            "mensaje": (f"No existe un pedido con el numero de seguimiento {tracking} en el "
                        "registro de EcoMarket. Pide al cliente revisar el numero; no "
                        "inventes datos de un pedido inexistente."),
        }

    # La respuesta expone los campos que el agente necesita para el dialogo y
    # para la siguiente herramienta. El nombre del cliente va solo como
    # inicial (menos datos personales en la traza de auditoria).
    productos = pedido["productos"]
    return {
        "exito": True,
        "pedido": {
            "tracking": pedido["tracking_number"],
            "cliente": pedido["cliente"].split()[0] + " " + pedido["cliente"].split()[-1][:1] + ".",
            "productos": productos,
            "total": pedido["total"],
            "estado": pedido["estado"],
            "fecha_entrega": pedido["fecha_entrega"],
            "transportadora": pedido["transportadora"],
        },
    }


@tool
def buscar_pedido(tracking: str) -> str:
    """Busca un pedido de EcoMarket por su numero de seguimiento.

    Args:
        tracking: numero de seguimiento del pedido, formato ECO-XXXXX
            (por ejemplo ECO-10005). Se acepta texto alrededor si contiene
            el patron.

    Returns:
        JSON con exito=True y el pedido (productos, estado, fechas) o con
        exito=False y un error explicito (formato_invalido o
        pedido_no_encontrado).
    """
    return json.dumps(buscar_pedido_core(tracking), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Herramienta 2: verificar elegibilidad de devolucion
# ---------------------------------------------------------------------------

def _dictamen(tracking, producto, motivo, pedido):
    """Motor de reglas de la politica (seccion 2 'Excepciones' y generales)."""
    fecha_hoy = hoy()
    tipo_motivo = _clasificar_motivo(motivo)

    # Caso especial del corpus: el pedido ya tiene una devolucion en
    # proceso (ECO-10007). El agente debe comunicarlo, no duplicar.
    if pedido["estado"] == "DEVOLUCION EN PROCESO":
        return {
            "elegible": False,
            "regla_aplicable": "devolucion_ya_en_proceso",
            "detalle": ("Este pedido ya tiene una devolucion en proceso: la etiqueta de retorno "
                        "ya fue enviada (ver notas del pedido). No se emite otra."),
            "tipo_motivo": tipo_motivo,
            "requiere_aclaracion": False,
        }

    if pedido["fecha_entrega"] is None:
        return {
            "elegible": False,
            "regla_aplicable": "pedido_no_entregado",
            "detalle": (f"El pedido aun no ha sido entregado (estado {pedido['estado']}); "
                        "la politica de devoluciones aplica desde la entrega."),
            "tipo_motivo": tipo_motivo,
            "requiere_aclaracion": False,
        }

    fecha_entrega = datetime.date.fromisoformat(pedido["fecha_entrega"])
    dias_transcurridos = (fecha_hoy - fecha_entrega).days

    base = {
        "tracking": tracking,
        "producto": producto,
        "dias_desde_entrega": dias_transcurridos,
        "tipo_motivo": tipo_motivo,
        "requiere_aclaracion": False,
    }

    if tipo_motivo == "defecto":
        # Excepcion de la politica: aplica a CUALQUIER categoria dentro de
        # los 7 dias siguientes a la entrega, con foto del problema.
        if dias_transcurridos <= PLAZO_DIAS_DEFECTO:
            return base | {
                "elegible": True,
                "regla_aplicable": "excepcion_defecto",
                "detalle": (f"Producto con defecto/dano/incorrecto dentro de los {PLAZO_DIAS_DEFECTO} dias "
                            "posteriores a la entrega (excepcion: aplica sin importar la categoria). "
                            "EcoMarket asume el costo del retorno. Se debe pedir foto del problema."),
            }
        return base | {
            "elegible": False,
            "regla_aplicable": "excepcion_defecto_fuera_de_plazo",
            "detalle": (f"Las devoluciones por defecto solo aplican dentro de los {PLAZO_DIAS_DEFECTO} dias "
                        f"posteriores a la entrega; han pasado {dias_transcurridos} dias."),
        }

    if tipo_motivo == "ambiguo":
        return base | {
            "elegible": False,
            "regla_aplicable": "motivo_no_clasificado",
            "detalle": ("El motivo no se puede clasificar como defecto ni como cambio de opinion. "
                        "No asumas: pregunta al cliente por el motivo exacto antes de continuar."),
            "requiere_aclaracion": True,
        }

    # Cambio de opinion (o motivo ya clasificado como no defecto): aplica la
    # via estandar, que exige que el producto sea devolvible por categoria.
    razon_exclusion = _regla_no_devoluble(producto, pedir_categoria(producto))
    if razon_exclusion:
        return base | {
            "elegible": False,
            "regla_aplicable": "categoria_no_devoluble",
            "detalle": (f"El producto no admite devolucion fuera del canal de defecto: {razon_exclusion}. "
                        "Recuerda al cliente la excepcion: si llego defectuoso, danado o incorrecto, "
                        f"SI se puede devolver dentro de los {PLAZO_DIAS_DEFECTO} dias de la entrega."),
        }

    if dias_transcurridos > PLAZO_DIAS_GENERAL:
        return base | {
            "elegible": False,
            "regla_aplicable": "fuera_de_plazo",
            "detalle": (f"El plazo general es de {PLAZO_DIAS_GENERAL} dias calendario desde la entrega; "
                        f"han pasado {dias_transcurridos} dias."),
        }

    return base | {
        "elegible": True,
        "regla_aplicable": "devolucion_estandar",
        "detalle": (f"Producto devolvible dentro del plazo general de {PLAZO_DIAS_GENERAL} dias desde la "
                    "entrega. Condiciones: sin usar y en su empaque original. Si no hubo defecto, "
                    "el costo del retorno lo asume el cliente."),
    }


def pedir_categoria(nombre_producto):
    """Devuelve la categoria del inventario para un nombre de producto."""
    inventario = _cargar_inventario()
    fila = inventario.get(nombre_producto)
    if fila:
        return fila["categoria"]
    # Busqueda tolerante: el nombre del pedido puede diferir del catalogo
    # (p.ej. 'Café orgánico molido 500g' del pedido esta en el inventario sin
    # el sufijo de la suscripcion). La coincidencia es bidireccional por
    # tokens para cubrir ambos sentidos de la abreviatura.
    for nombre, fila_busqueda in inventario.items():
        if (_frases_coinciden(nombre_producto, nombre)
                or _frases_coinciden(nombre, nombre_producto)):
            return fila_busqueda["categoria"]
    return None


def verificar_elegibilidad_core(tracking, producto, motivo):
    """Motor de elegibilidad. Ver contrato en el docstring de verificar_elegibilidad_devolucion."""
    resultado_pedido = buscar_pedido_core(tracking)
    if not resultado_pedido["exito"]:
        return resultado_pedido  # el error del pedido es la respuesta correcta aqui

    pedido = resultado_pedido["pedido"]
    if not producto or not producto.strip():
        return {
            "exito": False,
            "error": "producto_requerido",
            "mensaje": ("Falta el nombre del producto a devolver. Con base en buscar_pedido, "
                        "pide al cliente elegir entre sus productos: " + ", ".join(pedido["productos"])),
        }
    if motivo is None or not motivo.strip() or len(motivo.strip()) < 3:
        return {
            "exito": False,
            "error": "motivo_requerido",
            "mensaje": ("Falta el motivo de la devolucion (por ejemplo: llego defectuoso, "
                        "no me gusto, quiero otro producto). Pidelo al cliente antes de verificar."),
        }

    # El producto debe pertenecer al pedido: si no se reconoce entre el
    # contenido real del pedido, no se verifica contra el inventario.
    coincidencias = [
        nombre for nombre in pedido["productos"]
        if _frases_coinciden(producto, nombre)
    ]
    if not coincidencias:
        return {
            "exito": False,
            "error": "producto_no_encontrado_en_pedido",
            "mensaje": (f"El pedido contiene: {', '.join(pedido['productos'])}. Pide al cliente "
                        "confirmar el producto exacto; no verifiques un producto que no pertenece al pedido."),
        }
    if len(coincidencias) > 1:
        return {
            "exito": False,
            "error": "producto_ambiguo",
            "mensaje": ("El texto del cliente coincide con varios productos del pedido: "
                        "pide al cliente elegir uno: " + ", ".join(coincidencias)),
        }
    producto_confirmado = coincidencias[0]

    # El motor evalua contra el nombre CONFIRMADO del pedido (el texto libre
    # del cliente pudo venir abreviado y ya se normalizo al catalogo).
    dictamen = _dictamen(tracking, producto_confirmado, motivo, pedido)
    dictamen["producto_confirmado"] = producto_confirmado
    return {"exito": True, "dictamen": dictamen}


@tool
def verificar_elegibilidad_devolucion(tracking: str, producto: str, motivo: str) -> str:
    """Verifica si un producto de un pedido es elegible para devolucion segun la politica de EcoMarket.

    Args:
        tracking: numero de seguimiento del pedido (ECO-XXXXX), obtenido con buscar_pedido.
        producto: nombre del producto a devolver, tal como aparece en el pedido.
        motivo: motivo reportado por el cliente en lenguaje natural
            (por ejemplo 'llego defectuoso', 'no me gusto', 'quiero otro').

    Returns:
        JSON con exito=True y un dictamen estructurado {elegible:
        true/false, regla_aplicable, detalle, tipo_motivo, ...} o con
        exito=False y un error explicito (producto_requerido,
        motivo_requerido, producto_no_encontrado_en_pedido,
        producto_ambiguo, o el error del pedido).
    """
    return json.dumps(verificar_elegibilidad_core(tracking, producto, motivo), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Herramienta 3: generar etiqueta de devolucion
# ---------------------------------------------------------------------------

def _consecutivo_etiqueta():
    """Consecutivo siguiente para el numero de etiqueta (EL-001, EL-002, ...)."""
    registro = json.load(open(RUTA_ETIQUETAS, encoding="utf-8"))
    return len(registro["etiquetas"]) + 1


def generar_etiqueta_core(tracking, dictamen):
    """Emision de etiqueta. Ver contrato en el docstring de generar_etiqueta_devolucion."""
    tracking = (tracking or "").strip().upper()
    resultado = buscar_pedido_core(tracking)
    if not resultado["exito"]:
        return resultado

    pedido = resultado["pedido"]

    # Validacion del dictamen recibido: la herramienta exige el dictamen
    # estructurado que emitio verificar_elegibilidad_devolucion; no confia
    # en la prosa del agente (defensa en profundidad: doble revision).
    try:
        dictamen_datos = json.loads(dictamen) if isinstance(dictamen, str) else dictamen
    except (json.JSONDecodeError, TypeError):
        return {
            "exito": False,
            "error": "dictamen_invalido",
            "mensaje": ("El dictamen debe ser el JSON completo que devolvio "
                        "verificar_elegibilidad_devolucion (pasalo sin modificar ni resumir)."),
        }
    if not dictamen_datos.get("elegible") or dictamen_datos.get("tracking") not in (None, tracking):
        return {
            "exito": False,
            "error": "no_elegible_o_dictamen_incoherente",
            "mensaje": ("No se emite etiqueta: el dictamen no declara este pedido como elegible. "
                        "Nunca generes etiqueta sin un dictamen de elegibilidad positivo."),
        }

    # Re-verificacion interna con los datos actuales (defensa en profundidad):
    # si algo cambio entre el dictamen y la emision, se detecta aqui.
    re_verificacion = verificar_elegibilidad_core(
        tracking,
        dictamen_datos.get("producto_confirmado") or dictamen_datos.get("producto") or "",
        dictamen_datos.get("tipo_motivo") == "defecto" and "producto con defecto" or
        (dictamen_datos.get("detalle") or "cambio de opinion"),
    )
    if not re_verificacion["exito"] or not re_verificacion["dictamen"]["elegible"]:
        return {
            "exito": False,
            "error": "elegibilidad_no_reproducible",
            "mensaje": ("La re-verificacion interna de elegibilidad no coincide con el dictamen: "
                        "no se emite la etiqueta. Explica al cliente la regla actual."),
        }

    registro = json.load(open(RUTA_ETIQUETAS, encoding="utf-8")) if os.path.exists(RUTA_ETIQUETAS) else {"etiquetas": []}
    ya_emitida = next((et for et in registro["etiquetas"] if et["tracking"] == tracking), None)
    if ya_emitida:
        return {
            "exito": True,
            "duplicado": True,
            "mensaje": f"Esta etiqueta ya fue emitida en esta sesion: no se emite de nuevo.",
            "etiqueta": ya_emitida["etiqueta"],
        }

    numero = _consecutivo_etiqueta()
    etiqueta = {
        "numero_etiqueta": f"EL-{numero:03d}",
        "numero_guia": tracking.replace("ECO", "DEV") + f"-{numero:02d}",
        "transportadora": pedido["transportadora"],
        "direccion_recepcion": DIRECCION_DEVOLUCIONES,
        "enlace_pdf_simulado": f"https://etiquetas.ecomarket.co/{tracking}-dev.pdf",
    }
    registro["etiquetas"].append({
        "tracking": tracking,
        "producto": dictamen_datos.get("producto_confirmado"),
        "regla_aplicable": dictamen_datos.get("regla_aplicable"),
        "etiqueta": etiqueta,
        "emitida_en": hoy().isoformat(),
    })
    with open(RUTA_ETIQUETAS, "w", encoding="utf-8") as archivo:
        json.dump(registro, archivo, ensure_ascii=False, indent=2)

    return {
        "exito": True,
        "etiqueta": etiqueta,
        "mensaje": "Etiqueta emitida y registrada en data/etiquetas_emitidas.json (auditable).",
    }


@tool
def generar_etiqueta_devolucion(tracking: str, dictamen: str) -> str:
    """Emite la etiqueta de retorno para un pedido SI el dictamen de elegibilidad es positivo.

    Args:
        tracking: numero de seguimiento del pedido (ECO-XXXXX).
        dictamen: el JSON completo que devolvio verificar_elegibilidad_devolucion
            (sin modificar ni resumir); la herramienta lo revalida internamente.

    Returns:
        JSON con exito=True y {numero_etiqueta, numero_guia, transportadora,
        direccion_recepcion, enlace_pdf_simulado}, o exito=False con el error
        (dictamen_invalido, no_elegible_o_dictamen_incoherente,
        elegibilidad_no_reproducible, etc.).
    """
    return json.dumps(generar_etiqueta_core(tracking, dictamen), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registro de herramientas para el agente (orden en que se presentan)
# ---------------------------------------------------------------------------

HERRAMIENTAS = [buscar_pedido, verificar_elegibilidad_devolucion, generar_etiqueta_devolucion]