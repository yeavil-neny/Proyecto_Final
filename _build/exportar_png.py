# -*- coding: utf-8 -*-
"""Utileria interna: armar pagina minima (CSS del visor + SVG) para el PNG de docs/.

El HTML entregado por archify estiliza el SVG con hojas de clase; para un PNG
estandarte se une el CSS del artefacto con el bloque SVG ya extraido, en una
pagina minima con fondo claro, y Chrome headless la fotografiza.
"""
import os
import re

RAIZ_DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
HTML = os.path.join(RAIZ_DOCS, "flujo-devolucion-agente.html")
SVG = os.path.join(RAIZ_DOCS, "assets", "flujo-devolucion-agente.svg")
MINIMA = os.path.join(os.path.dirname(SVG), "_render_svg.html")

pagina = open(HTML, encoding="utf-8").read()
svg = open(SVG, encoding="utf-8").read()

estilos = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", pagina, flags=re.S))
if not estilos.strip():
    raise SystemExit("No se encontro CSS en el artefacto entregado.")

# El CSS del visor esta escrito para su DOM completo; se envuelve aqui en
# <style> porque la captura toma solo el contenido interno de los bloques.
# El tema del diagrama vive en svg[data-theme="..."]: el visor lo define en
# tiempo de ejecucion y aqui se fuerza el claro para el PNG de la documentacion.
svg = svg.replace("<svg ", '<svg data-theme="light" ', 1) if "data-theme=" not in svg.split(">", 1)[0] else svg
html_minimo = (
    "<!doctype html><head><meta charset='utf-8'><style>"
    + estilos +
    "</style><style>body{margin:0 !important;background:#ffffff !important}"
    "html,body,div{overflow:hidden}</style></head>"
    "<body><div style='width:1363px;height:776px;background:#ffffff;overflow:hidden'>"
    + svg +
    "</div></body>"
)
open(MINIMA, "w", encoding="utf-8").write(html_minimo)
print("Pagina minima lista:", MINIMA)