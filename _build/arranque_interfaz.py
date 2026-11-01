# -*- coding: utf-8 -*-
"""Prueba de arranque de la interfaz Streamlit (sin navegador y sin API).

Ejecuta la pagina con el framework de pruebas de Streamlit (AppTest): carga
la configuracion, renderiza el historial vacio y deja el campo de entrada
listo. La construccion del agente corre aqui (embeddings y base vectorial)
pero no realiza llamadas al LLM, sin gasto de cuota.

Uso: python _build/arranque_interfaz.py
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.join(RAIZ, "src", "app_devoluciones.py"), default_timeout=240)
at.run()

if at.exception:
    print("La pagina levanto con excepciones:")
    for excepcion in at.exception:
        print(f"  {excepcion.value}")
    sys.exit(1)

if not at.chat_input:
    print("No hay campo de consulta en la pagina.")
    sys.exit(1)

if not at.session_state.get("mensajes") is not None:
    print("No hay estado de conversacion inicializado.")
    sys.exit(1)

print(f"OK arranque: botones de ejemplo: {len(at.sidebar.button)}; campo de consulta listo; sin excepciones.")