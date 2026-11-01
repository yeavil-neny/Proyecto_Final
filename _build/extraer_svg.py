# -*- coding: utf-8 -*-
"""Utileria interna: extrae el SVG del diagrama validado para incrustarlo en docs/.

Construido con archify (docs/flujo-devolucion-agente.html contiene exactamente
un bloque SVG; la validacion lo comprobo). Guarda el SVG en
docs/assets/flujo-devolucion-agente.svg con ladeclaracion de namespace raiz.
"""
import os
import re

HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "docs", "flujo-devolucion-agente.html")
SALIDA = os.path.join(os.path.dirname(HTML), "assets", "flujo-devolucion-agente.svg")

html = open(HTML, encoding="utf-8").read()

coincidencias = re.findall(r"<svg.*?</svg>", html, flags=re.S)
if len(coincidencias) != 1:
    raise SystemExit(f"Se esperaba exactamente 1 bloque SVG; hay {len(coincidencias)}.")

svg = coincidencias[0]
if "xmlns=" not in svg.split(">", 1)[0]:
    svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
open(SALIDA, "w", encoding="utf-8").write(("\n".join(line for line in svg.splitlines() if line.strip()) + "\n").replace(" xmlns=\"\" ", " "))
print("SVG extraido:", SALIDA, len(svg), "caracteres")