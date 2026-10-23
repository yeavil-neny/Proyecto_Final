# -*- coding: utf-8 -*-
"""
Casos de prueba deterministas del agente de devoluciones de EcoMarket
(Fase 2 del Proyecto Final).

Evaluan SIN llamar al LLM y sin API key:
  1. el router (src/agente.py): consultas reales -> ruta esperada;
  2. las herramientas (src/herramientas.py): contratos, reglas de la
     politica, errores esperados y la auditoria de etiquetas.

El reloj simulado queda fijado al corpus (fecha_base 2026-09-17 de
data/pedidos.json). Los resultados alimentan el documento
docs/fase2-implementacion.md (tabla de casos) y el video de la demo.

Uso:
  python src/pruebas_fase2.py            # ejecuta todos los casos
  python src/pruebas_fase2.py --detalle  # imprime la salida JSON de cada caso

Sale con codigo 0 si todos los casos pasan; nonzero si alguno falla.
"""

import argparse
import json
import sys

import agente
import herramientas


FALLOS = []


def _registrar(nombre, condicion, detalle=""):
    estado = "PASA" if condicion else "Falló"
    print(f"  [{estado}] {nombre}" + (f"  ({detalle})" if detalle else ""))
    if not condicion:
        FALLOS.append(nombre)


def _resumen(resultado):
    """Linea compacta de un JSON de herramienta para mostrarlo en cada caso."""
    return json.dumps(resultado, ensure_ascii=False)[:180]


# ---------------------------------------------------------------------------
# 1. Router: enrutamiento de consultas (decision 3.1 de la propuesta)
# ---------------------------------------------------------------------------

CASOS_ROUTER = [
    # (consulta, ruta esperada, razon del caso)
    ("Quiero devolver la vela del pedido ECO-10007, llegó defectuosa", "accion", "orden con tracking"),
    ("Mi shampoo llegó dañado, necesito devolverlo", "accion", "orden con defecto, sin tracking"),
    ("Devuelve mi pedido ECO-10005", "accion", "imperativo con tracking"),
    ("Me llegó roto el bálsamo del pedido ECO-10012, quiero la etiqueta de devolución", "accion", "orden con defecto y etiqueta"),
    ("¿Cuál es el estado del pedido ECO-10003?", "informativa", "pregunta de estado"),
    ("¿Cómo solicito una devolución?", "informativa", "pregunta sobre el proceso"),
    ("¿Qué productos no se pueden devolver?", "informativa", "pregunta sobre la política"),
    ("¿Puedo devolver mi shampoo del pedido ECO-10004?", "informativa", "pregunta condicional (no ejecuta)"),
    ("¿Cuál es el plazo de devolución?", "informativa", "pregunta sobre el plazo"),
    ("Necesito una devolución del pedido ECO-10009", "accion", "primera persona + sustantivo"),
    ("Hola, ¿qué tal?", "informativa", "saludo sin orden"),
]


def probar_router(detalle):
    print("\n1. Router (reglas de entrada deterministas)")
    for consulta, ruta_esperada, razon in CASOS_ROUTER:
        ruta, justificacion = agente.enrutar(consulta)
        _registrar(f"\"{consulta}\" -> {ruta_esperada}", ruta == ruta_esperada,
                   f"[{razon}; router: {justificacion}]")


# ---------------------------------------------------------------------------
# 2. Herramienta 1: buscar_pedido
# ---------------------------------------------------------------------------

def probar_buscar_pedido(detalle):
    print("\n2. buscar_pedido (contrato y errores)")

    r = herramientas.buscar_pedido_core("ECO-10005")
    _registrar("pedido existente devuelve exito con estado ENTREGADO",
               r["exito"] and r["pedido"]["estado"] == "ENTREGADO", _resumen(r))
    if detalle:
        print(f"        {json.dumps(r, ensure_ascii=False)}")

    r = herramientas.buscar_pedido_core("pedido Eco-10005")
    _registrar("acepta texto alrededor del patron (rescata ECO-10005)",
               r["exito"] and r["pedido"]["tracking"] == "ECO-10005", _resumen(r))

    r = herramientas.buscar_pedido_core("12345")
    _registrar("formato invalido da error explicito formato_invalido",
               not r["exito"] and r["error"] == "formato_invalido", _resumen(r))

    r = herramientas.buscar_pedido_core("ECO-99999")
    _registrar("pedido inexistente da error explicito pedido_no_encontrado",
               not r["exito"] and r["error"] == "pedido_no_encontrado", _resumen(r))

    r = herramientas.buscar_pedido_core("")
    _registrar("argumento vacio da formato_invalido (no crash)",
               not r["exito"] and r["error"] == "formato_invalido", _resumen(r))


# ---------------------------------------------------------------------------
# 3. Herramienta 2: verificar_elegibilidad_devolucion (motor de reglas)
# ---------------------------------------------------------------------------

def probar_elegibilidad(detalle):
    print("\n3. verificar_elegibilidad_devolucion (motor de reglas de la politica)")

    # Elegible por la via estandar: producto Hogar (devolvible), entregado
    # hoy del reloj simulado, 30 dias completos por delante.
    r = herramientas.verificar_elegibilidad_core("ECO-10005", "envases de vidrio", "ya no lo necesito")
    d = r.get("dictamen", {})
    _registrar("ECO-10005 envases de vidrio + cambio de opinion -> elegible (via estandar, costo cliente)",
               r["exito"] and d.get("elegible") and d.get("regla_aplicable") == "devolucion_estandar"
               and "cliente" in d.get("detalle", ""), _resumen(r))

    # Defecto dentro de 7 dias de entrega (ECO-10001: entregado 09-11, reloj 09-17).
    r = herramientas.verificar_elegibilidad_core("ECO-10001", "cepillos", "llegaron defectuosos")
    d = r.get("dictamen", {})
    _registrar("ECO-10001 cepillos defectuosos (6 dias de entrega) -> elegible por excepcion de defecto",
               r["exito"] and d.get("elegible") and d.get("regla_aplicable") == "excepcion_defecto", _resumen(r))

    # La excepcion de defecto ALCANZA categorias no devolvibles (politica, seccion Excepciones).
    r = herramientas.verificar_elegibilidad_core("ECO-10006", "cafe", "llego dañado")
    d = r.get("dictamen", {})
    _registrar("ECO-10006 cafe (alimentos, no devoluble) defectuoso en 4 dias -> elegible por la excepcion",
               r["exito"] and d.get("elegible") and d.get("regla_aplicable") == "excepcion_defecto", _resumen(r))

    # La misma categoria por cambio de opinion SI se rechaza (contraste clave).
    r = herramientas.verificar_elegibilidad_core("ECO-10006", "cafe", "no me gusto")
    d = r.get("dictamen", {})
    _registrar("ECO-10006 cafe + no me gusto -> NO elegible (categoria_no_devoluble)",
               r["exito"] and not d.get("elegible") and d.get("regla_aplicable") == "categoria_no_devoluble", _resumen(r))

    # Higiene no devoluble (shampoo/crema: seccion 2 de la politica).
    r = herramientas.verificar_elegibilidad_core("ECO-10004", "shampoo", "no me funciono bien")
    d = r.get("dictamen", {})
    _registrar("ECO-10004 shampoo no me funciono -> NO elegible y NO entregado (pedido_no_entregado)",
               r["exito"] and not d.get("elegible") and d.get("regla_aplicable") == "pedido_no_entregado", _resumen(r))

    # Defecto fuera del plazo de 7 dias: ECO-10007 (entregado 09-09, 8 dias al 09-17)
    # pero ya tenia devolucion en proceso: gana la regla de no duplicar.
    r = herramientas.verificar_elegibilidad_core("ECO-10007", "vela", "llegó defectuosa")
    d = r.get("dictamen", {})
    _registrar("ECO-10007 vela defectuosa -> NO elegible (devolucion_ya_en_proceso)",
               r["exito"] and not d.get("elegible") and d.get("regla_aplicable") == "devolucion_ya_en_proceso", _resumen(r))

    # Semillas: exclusion por nombre aunque la categoria sea Despensa.
    r = herramientas.verificar_elegibilidad_core("ECO-10011", "semillas", "no me gusto")
    d = r.get("dictamen", {})
    _registrar("ECO-10011 semillas + cambio de opinion -> NO elegible (semillas y plantas)",
               r["exito"] and not d.get("elegible") and d.get("regla_aplicable") == "categoria_no_devoluble", _resumen(r))

    # Motivo ambiguo: pide aclaracion en lugar de asumir (comportamiento acordado).
    r = herramientas.verificar_elegibilidad_core("ECO-10005", "envases", "bueno, es que...")
    d = r.get("dictamen", {})
    _registrar("motivo ambiguo -> dictamen requiere_aclaracion (el agente debe preguntar)",
               r["exito"] and d.get("requiere_aclaracion") and d.get("regla_aplicable") == "motivo_no_clasificado", _resumen(r))

    # Errores de contrato.
    r = herramientas.verificar_elegibilidad_core("eco-10005", "casa", "cambio de opinion")
    _registrar("producto que no esta en el pedido -> producto_no_encontrado_en_pedido",
               not r["exito"] and r["error"] == "producto_no_encontrado_en_pedido", _resumen(r))

    r = herramientas.verificar_elegibilidad_core("ECO-10005", "", "no me gusto")
    _registrar("producto vacio -> producto_requerido",
               not r["exito"] and r["error"] == "producto_requerido", _resumen(r))

    r = herramientas.verificar_elegibilidad_core("ECO-10005", "envases", "")
    _registrar("motivo vacio -> motivo_requerido",
               not r["exito"] and r["error"] == "motivo_requerido", _resumen(r))


# ---------------------------------------------------------------------------
# 4. Herramienta 3: generar_etiqueta_devolucion (emision + auditoria)
# ---------------------------------------------------------------------------

def probar_etiqueta(detalle):
    print("\n4. generar_etiqueta_devolucion (emision vigilada y registro auditable)")

    dictamen_bueno = json.dumps(herramientas.verificar_elegibilidad_core(
        "ECO-10005", "envases", "ya no lo necesito")["dictamen"], ensure_ascii=False)

    r = herramientas.generar_etiqueta_core("ECO-10005", dictamen_bueno)
    etiqueta = r.get("etiqueta", {})
    _registrar("dictamen elegible -> emite etiqueta con numero y guia",
               r["exito"] and etiqueta.get("numero_etiqueta", "").startswith("EL-")
               and etiqueta.get("numero_guia", "").startswith("DEV"), _resumen(r))
    if detalle:
        print(f"        {json.dumps(r, ensure_ascii=False)}")

    r2 = herramientas.generar_etiqueta_core("ECO-10005", dictamen_bueno)
    _registrar("segunda emision del mismo pedido -> no duplica (devuelve la ya emitida)",
               r2["exito"] and r2.get("duplicado") and r2["etiqueta"] == etiqueta, _resumen(r2))

    r = herramientas.generar_etiqueta_core("ECO-10006", "{\"elegible\": true}")
    _registrar("dictamen improvisado por el agente (sin verificacion) -> dictamen_invalido o no elegible",
               not r["exito"], _resumen(r))

    dictamen_negativo = json.dumps(herramientas.verificar_elegibilidad_core(
        "ECO-10006", "cafe", "no me gusto")["dictamen"], ensure_ascii=False)
    r = herramientas.generar_etiqueta_core("ECO-10006", dictamen_negativo)
    _registrar("dictamen con elegible=false -> no emite (no_elegible_o_dictamen_incoherente)",
               not r["exito"], _resumen(r))

    r = herramientas.generar_etiqueta_core("esto no es un dictamen", "{}")
    _registrar("tracking inexistente -> pedido_no_encontrado",
               not r["exito"] and r["error"] in ("pedido_no_encontrado", "formato_invalido"), _resumen(r))

    # Auditoria: la etiqueta emitida quedo registrada con fecha simulada.
    registro = json.load(open(herramientas.RUTA_ETIQUETAS, encoding="utf-8"))
    emitidas = [e for e in registro["etiquetas"] if e["tracking"] == "ECO-10005"]
    _registrar("la etiqueta emitida quedo registrada en data/etiquetas_emitidas.json",
               len(emitidas) == 1 and emitidas[0]["regla_aplicable"] == "devolucion_estandar", _resumen(emitidas[0] if emitidas else {}))


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Casos de prueba deterministas de la Fase 2")
    parser.add_argument("--detalle", action="store_true", help="imprime la salida JSON completa de cada caso")
    args = parser.parse_args()

    total = 0
    probar_router(args.detalle)
    probar_buscar_pedido(args.detalle)
    probar_elegibilidad(args.detalle)
    probar_etiqueta(args.detalle)

    if FALLOS:
        print(f"\nResultado: {len(FALLOS)} caso(s) falló: {', '.join(FALLOS)}")
        sys.exit(1)
    print("\nResultados: todos los casos pasan.")

    # La corrida dejo emisiones de prueba en data/etiquetas_emitidas.json: se
    # restablece el registro vacio (estado inicial del repo) para que las
    # siguientes ejecuciones (p.ej. la demo grabada) partan de cero.
    registro = json.load(open(herramientas.RUTA_ETIQUETAS, encoding="utf-8"))
    if registro.get("etiquetas"):
        registro["etiquetas"] = []
        with open(herramientas.RUTA_ETIQUETAS, "w", encoding="utf-8") as archivo:
            json.dump(registro, archivo, ensure_ascii=False, indent=2)
        print("(Registro de etiquetas de prueba restablecido a vacio.)")


if __name__ == "__main__":
    main()