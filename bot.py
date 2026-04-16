#!/usr/bin/env python3
"""
Bot de Telegram — La Voz del Alma
Motor: Groq (gratis) — LLaMA 3 para texto, Whisper para voz
Plataformas: Instagram + Facebook vía Meta Graph API
Deploy: Railway
"""

import os
import json
import logging
import tempfile
import urllib.request
import urllib.parse
import urllib.error

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from groq import Groq

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Credenciales desde variables de entorno ───────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
PATY_CHAT_ID   = os.environ.get("PATY_CHAT_ID", "")   # seguridad: solo Paty

IG_USER_ID    = os.environ["IG_USER_ID"]
IG_TOKEN      = os.environ["IG_TOKEN"]
FB_PAGE_ID    = os.environ["FB_PAGE_ID"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]

# ── Cliente Groq ──────────────────────────────────────────────────────────────
groq = Groq(api_key=GROQ_API_KEY)

# ── Identidad de Paty (contexto para el LLM) ──────────────────────────────────
SYSTEM_PROMPT = """Eres el asistente personal de Paty Godínez, creadora de la marca
"La Voz del Alma". Ayudas a gestionar sus redes sociales desde Telegram.

Sobre Paty:
- Coach de vida y bienestar emocional
- Tono: cercano, empático, profundo, inspirador
- Audiencia: mujeres 30-50 años buscando bienestar y crecimiento personal
- Plataformas: Instagram (@patygodinezcoach) y Facebook (Paty Godinez I Coach de Vida)
- Pilares de contenido: regulación emocional, propósito, relaciones sanas, espiritualidad práctica
- Hashtags principales: #regulacionemocional #bienestaremocional #crecimientopersonal #lavorzdelalma #patygodinezcoach

Responde siempre en español, de forma concisa y accionable.
Cuando generes captions, usa máximo 2200 caracteres y cierra con hashtags relevantes."""

# ── Seguridad: solo Paty puede usar el bot ───────────────────────────────────
def es_paty(update: Update) -> bool:
    if not PATY_CHAT_ID:
        return True  # sin restricción si no está configurado
    return str(update.effective_user.id) == str(PATY_CHAT_ID)

# ── Helpers de Meta API ───────────────────────────────────────────────────────
def meta_post(url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def publicar_instagram(image_url: str, caption: str) -> str:
    base = f"https://graph.instagram.com/v19.0/{IG_USER_ID}"
    r1 = meta_post(f"{base}/media", {
        "image_url": image_url,
        "caption": caption,
        "access_token": IG_TOKEN,
    })
    if "id" not in r1:
        raise RuntimeError(r1.get("error", {}).get("message", str(r1)))
    r2 = meta_post(f"{base}/media_publish", {
        "creation_id": r1["id"],
        "access_token": IG_TOKEN,
    })
    if "id" not in r2:
        raise RuntimeError(r2.get("error", {}).get("message", str(r2)))
    return r2["id"]

def publicar_facebook(image_url: str, caption: str) -> str:
    r = meta_post(
        f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
        {"url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN},
    )
    if "id" not in r:
        raise RuntimeError(r.get("error", {}).get("message", str(r)))
    return r["id"]

# ── LLM con Groq ─────────────────────────────────────────────────────────────
def preguntar_groq(mensaje: str, extra_system: str = "") -> str:
    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    resp = groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system",  "content": system},
            {"role": "user",    "content": mensaje},
        ],
        max_tokens=1024,
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

# ── Transcripción de voz con Whisper/Groq ─────────────────────────────────────
async def transcribir_audio(file_path: str) -> str:
    with open(file_path, "rb") as f:
        transcription = groq.audio.transcriptions.create(
            file=(os.path.basename(file_path), f),
            model="whisper-large-v3-turbo",
            language="es",
        )
    return transcription.text.strip()

# ── Comandos ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text(
        "✨ *Hola Paty* — Soy tu asistente de La Voz del Alma.\n\n"
        "Puedo ayudarte a:\n"
        "📝 `/caption` — Generar un caption para Instagram/Facebook\n"
        "💡 `/ideas` — Ideas de contenido para hoy\n"
        "📸 `/publicar` — Publicar en redes (necesito URL de imagen + caption)\n"
        "🎙 Mándame un *audio* y te lo transcribo + proceso\n"
        "💬 O simplemente escríbeme lo que necesitas",
        parse_mode="Markdown",
    )

async def cmd_caption(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    tema = " ".join(ctx.args) if ctx.args else ""
    if not tema:
        await update.message.reply_text(
            "¿Sobre qué quieres el caption? Escríbelo así:\n"
            "`/caption el poder de soltar lo que no te pertenece`",
            parse_mode="Markdown",
        )
        return
    await update.message.reply_text("✍️ Generando caption...")
    try:
        caption = preguntar_groq(
            f"Escribe un caption emotivo y poderoso para Instagram sobre: {tema}",
            extra_system="El caption debe tener entre 150-300 palabras, un hook inicial fuerte, desarrollo emotivo, llamada a la acción y cierre con hashtags."
        )
        await update.message.reply_text(caption)
    except Exception as e:
        logger.error(f"Error generando caption: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text("💡 Generando ideas para hoy...")
    try:
        ideas = preguntar_groq(
            "Dame 5 ideas de contenido originales para hoy en Instagram y Facebook. "
            "Para cada idea incluye: formato (reel/carrusel/foto/texto), hook inicial y por qué conectaría con la audiencia."
        )
        await update.message.reply_text(ideas)
    except Exception as e:
        logger.error(f"Error generando ideas: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_publicar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text(
        "Para publicar necesito que me envíes:\n\n"
        "1️⃣ La *URL de la imagen* (que esté pública en internet)\n"
        "2️⃣ El *caption* (texto del post)\n"
        "3️⃣ Las *plataformas*: instagram, facebook, o ambas\n\n"
        "Envíalo todo junto así:\n"
        "`URL: https://...\nCAPTION: Tu texto aquí\nPLATAFORMAS: ambas`",
        parse_mode="Markdown",
    )

async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text(
        "🌿 *La Voz del Alma — Comandos disponibles*\n\n"
        "/start — Saludo inicial\n"
        "/caption [tema] — Genera un caption\n"
        "/ideas — 5 ideas de contenido\n"
        "/publicar — Instrucciones para publicar\n"
        "/ayuda — Este menú\n\n"
        "También puedes:\n"
        "🎙 Enviar un *audio* para transcribirlo y procesarlo\n"
        "💬 Escribir libremente y te respondo como asistente",
        parse_mode="Markdown",
    )

# ── Mensajes de texto libre ───────────────────────────────────────────────────
async def handle_texto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    texto = update.message.text.strip()

    # Detectar formato de publicación directa
    if "URL:" in texto and "CAPTION:" in texto:
        await procesar_publicacion(update, texto)
        return

    # Respuesta libre con Groq
    await update.message.reply_text("🤔 Procesando...")
    try:
        respuesta = preguntar_groq(texto)
        await update.message.reply_text(respuesta)
    except Exception as e:
        logger.error(f"Error en handle_texto: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def procesar_publicacion(update: Update, texto: str):
    """Parsea el formato URL/CAPTION/PLATAFORMAS y publica."""
    lines = {k.strip(): v.strip() for line in texto.splitlines()
             if ":" in line for k, v in [line.split(":", 1)]}
    image_url  = lines.get("URL", "")
    caption    = lines.get("CAPTION", "")
    plataforma = lines.get("PLATAFORMAS", "ambas").lower()

    if not image_url or not caption:
        await update.message.reply_text("❌ Falta URL o CAPTION. Revisa el formato.")
        return

    await update.message.reply_text("📤 Publicando...")
    resultados = []

    if plataforma in ("instagram", "ambas", "ig"):
        try:
            post_id = publicar_instagram(image_url, caption)
            resultados.append(f"✅ *Instagram* — Publicado!\n🔗 https://www.instagram.com/patygodinezcoach/")
        except Exception as e:
            resultados.append(f"❌ *Instagram* — Error: {e}")

    if plataforma in ("facebook", "ambas", "fb"):
        try:
            post_id = publicar_facebook(image_url, caption)
            resultados.append(f"✅ *Facebook* — Publicado!\n🔗 https://www.facebook.com/patygodinezcoach")
        except Exception as e:
            resultados.append(f"❌ *Facebook* — Error: {e}")

    await update.message.reply_text("\n\n".join(resultados), parse_mode="Markdown")

# ── Mensajes de voz ───────────────────────────────────────────────────────────
async def handle_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text("🎙 Transcribiendo tu mensaje de voz...")
    try:
        voice = update.message.voice or update.message.audio
        tg_file = await voice.get_file()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await tg_file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        texto_transcrito = await transcribir_audio(tmp_path)
        os.unlink(tmp_path)

        await update.message.reply_text(f"📝 *Transcripción:*\n_{texto_transcrito}_", parse_mode="Markdown")

        # Procesar el texto transcrito con Groq
        await update.message.reply_text("💭 Procesando tu mensaje...")
        respuesta = preguntar_groq(texto_transcrito)
        await update.message.reply_text(respuesta)

    except Exception as e:
        logger.error(f"Error en handle_audio: {e}")
        await update.message.reply_text(f"❌ Error al procesar audio: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("caption",  cmd_caption))
    app.add_handler(CommandHandler("ideas",    cmd_ideas))
    app.add_handler(CommandHandler("publicar", cmd_publicar))
    app.add_handler(CommandHandler("ayuda",    cmd_ayuda))
    app.add_handler(CommandHandler("help",     cmd_ayuda))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,   handle_audio))

    logger.info("🤖 Bot La Voz del Alma iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
