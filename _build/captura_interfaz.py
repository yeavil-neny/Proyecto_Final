# -*- coding: utf-8 -*-
"""Utileria interna: captura de pantalla real de la interfaz de la Fase 4.

Abre la app ya servida por Streamlit (puerto 8501), espera a que la pagina
termine de renderizar (el campo de chat aparece) y fotografiza. Usa el
Chrome instalado en el equipo por el canal "chrome" de Playwright: no
descarga ningun navegador nuevo.

Uso: python _build/captura_interfaz.py
"""
import sys
from playwright.sync_api import sync_playwright

SALIDA = r"C:\Repos\IA\CloudCodeProject\IA_GEN\Proyecto_Final\docs\evidencias\interfaz-streamlit.png"

with sync_playwright() as p:
    navegador = p.chromium.launch(channel="chrome", headless=True)
    pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
    pagina.goto("http://localhost:8501", timeout=120_000)
    # La pagina esta completa cuando el campo de conversacion responde.
    pagina.wait_for_selector('[data-testid="stChatInput"]', timeout=180_000)
    pagina.screenshot(path=SALIDA)
    navegador.close()

print("Captura guardada en", SALIDA)