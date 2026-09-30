"""
Monitor de convocatorias / eventos en Santander -> alertas por Telegram.
Fuentes: búsquedas RSS de Google News + feeds RSS de cuentas de X/Instagram.

Uso:
  python monitor_santander.py            -> bucle continuo (tu PC)
  python monitor_santander.py --una-vez  -> una pasada y sale (GitHub Actions)

Requisitos: pip install feedparser requests
"""
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

import feedparser
import requests

# ================= CONFIG =================
# En tu PC puedes escribirlos aquí; en GitHub se leen de los Secrets.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8241968851:AAHw7ggwElC45_WZChQ0iZ2c4rnTitOwkCQ")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1983227881")
INTERVALO_SEG = 300          # solo modo bucle: cada 5 min
VENTANA = "when:2d"          # noticias de los últimos 2 días

BUSQUEDAS = [
    '(concentración OR manifestación OR protesta OR convocatoria) Santander',
    '(Maricarmen OR "Mari Carmen") (Santander OR Cantabria)',
    '(desahucio OR "fondos buitre" OR vivienda) (concentración OR protesta) Cantabria',
    'site:eldiariomontanes.es (concentración OR manifestación)',
    'site:eldiario.es/cantabria (concentración OR manifestación OR protesta)',
    '"Sindicato de Vivienda de Cantabria"',
    '"Peñacastillo" (fondo OR desahucio OR vecinas)',
    'site:elfaradio.com (concentración OR manifestación)',
    'site:ifomo.es Santander (concentración OR manifestación)',
    '"Plaza Porticada" (acampada OR concentración OR asamblea)',
    '"Sindicato de Estudiantes" Santander (acampada OR concentración OR huelga)',
    '"Hermanos Calderón" Santander',
]

# RSS nativo de medios locales (gratis, sin RSS.app). Si alguno falla, se ignora.
FEEDS_MEDIOS = [
    "https://www.elfaradio.com/feed/",   # El Faradio (Santander)
]

# Feeds RSS de cuentas de X / Instagram (RSS.app o similar). Vacío = no se usa.
FEEDS_CUENTAS = [
    # "https://rss.app/feeds/XXXX.xml",  # PAH Cantabria (X)
]

PALABRAS_CLAVE = [
    "concentración", "concentracion", "manifestación", "manifestacion",
    "protesta", "convoca", "movilización", "movilizacion", "marcha",
    "desahucio", "maricarmen", "mari carmen", "acampada", "asamblea abierta",
    "fondo buitre", "fondos buitre", "cacerolada", "huelga", "huelga general",
]
ZONA = ["santander", "cantabria", "cántabr", "cantabr"]

ESTADO = Path(__file__).with_name("vistos.json")
# ==========================================


def cargar_vistos():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return []


def guardar_vistos(vistos):
    ESTADO.write_text(json.dumps(vistos[-3000:], ensure_ascii=False))


def url_gnews(q):
    return ("https://news.google.com/rss/search?q="
            + urllib.parse.quote(f"{q} {VENTANA}") + "&hl=es&gl=ES&ceid=ES:es")


def tiene(texto, lista):
    t = texto.lower()
    return any(k in t for k in lista)


def enviar_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=15,
        )
        if not r.ok:
            print("Telegram respondió:", r.text)
    except requests.RequestException as e:
        print("Error Telegram:", e)


def procesar(entries, vistos, set_vistos, filtro, icono, primera_vez):
    nuevos = 0
    for e in entries:
        uid = e.get("id") or e.get("link")
        if not uid or uid in set_vistos:
            continue
        set_vistos.add(uid)
        vistos.append(uid)
        texto = f"{e.get('title', '')} {e.get('summary', '')}"
        if primera_vez or not filtro(texto):
            continue
        fuente = e.get("source", {}).get("title", "")
        enviar_telegram(f"{icono} {e.get('title', '')[:250]}\n{fuente}\n{e.get('link', '')}")
        nuevos += 1
    return nuevos


def revisar(vistos, primera_vez):
    set_vistos = set(vistos)
    nuevos = 0
    for q in BUSQUEDAS:
        # Búsquedas site: ya son locales -> solo filtro de palabras
        if "site:" in q:
            filtro = lambda t: tiene(t, PALABRAS_CLAVE)
        else:
            filtro = lambda t: tiene(t, PALABRAS_CLAVE) and tiene(t, ZONA)
        nuevos += procesar(feedparser.parse(url_gnews(q)).entries,
                           vistos, set_vistos, filtro, "📢", primera_vez)
    for url in FEEDS_MEDIOS:
        nuevos += procesar(feedparser.parse(url).entries, vistos, set_vistos,
                           lambda t: tiene(t, PALABRAS_CLAVE), "📰", primera_vez)
    for url in FEEDS_CUENTAS:
        nuevos += procesar(feedparser.parse(url).entries, vistos, set_vistos,
                           lambda t: tiene(t, PALABRAS_CLAVE), "📲", primera_vez)
    return nuevos


def main():
    vistos = cargar_vistos()
    primera_vez = len(vistos) == 0
    if primera_vez:
        enviar_telegram("✅ Monitor Santander arrancado.")

    if "--una-vez" in sys.argv:
        n = revisar(vistos, primera_vez)
        guardar_vistos(vistos)
        print(f"Nuevos: {n}")
        return

    while True:
        try:
            n = revisar(vistos, primera_vez)
            guardar_vistos(vistos)
            print(time.strftime("%H:%M"), f"nuevos: {n}")
        except Exception as ex:
            print("Error:", ex)
        primera_vez = False
        time.sleep(INTERVALO_SEG)


if __name__ == "__main__":
    main()
