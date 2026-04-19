#!/usr/bin/env python3
"""
Bot de Telegram — La Voz del Alma v3.0
Flujo: Idea → Caption + Diseño → Preview → Aprobación → Publicación
Motor IA: OpenRouter (primary) + Groq (fallback) | Audio: Whisper/Groq
Imágenes: Pillow | Deploy: Oracle Cloud / Railway / Docker
"""

import os
import json
import logging
import tempfile
import random
import re
import io
import base64
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from groq import Groq
from PIL import Image, ImageDraw, ImageFont

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Credenciales ────────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
GROQ_API_KEY      = os.environ["GROQ_API_KEY"]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
PATY_CHAT_ID      = os.environ.get("PATY_CHAT_ID", "")

IG_USER_ID    = os.environ["IG_USER_ID"]
IG_TOKEN      = os.environ["IG_TOKEN"]
FB_PAGE_ID    = os.environ["FB_PAGE_ID"]
FB_PAGE_TOKEN = os.environ["FB_PAGE_TOKEN"]
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")

# Modelo de OpenRouter (deepseek-chat-v3 es gratis)
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free")
GROQ_MODEL       = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# ── Cliente Groq (para Whisper y fallback de texto) ─────────────────
groq_client = Groq(api_key=GROQ_API_KEY)

# ── Rutas de fuentes ────────────────────────────────────────────────
FONTS_DIR   = Path(__file__).parent / "fonts"
FONT_TITLE  = str(FONTS_DIR / "bruney-season.otf")
FONT_SCRIPT = str(FONTS_DIR / "New-Icon-Script.otf")

# ══════════════════════════════════════════════════════════════════════
#  IDENTIDAD DE MARCA
# ══════════════════════════════════════════════════════════════════════

TEMPLATES = [
    {"name": "crema",     "bg": "#f0eade", "text": "#4c513a", "accent": "#84472a"},
    {"name": "bosque",    "bg": "#4c513a", "text": "#f0eade", "accent": "#bab281"},
    {"name": "terracota", "bg": "#84472a", "text": "#f0eade", "accent": "#d9b094"},
    {"name": "lavanda",   "bg": "#eacce8", "text": "#4c513a", "accent": "#d1b4d0"},
    {"name": "salvia",    "bg": "#7e836f", "text": "#f0eade", "accent": "#a2ab8c"},
]

SYSTEM_PROMPT = """Eres el motor creativo de "La Voz del Alma", la marca personal de Paty Godínez.

SOBRE PATY:
- Psicóloga, coach, experta en mindfulness, neurociencias aplicadas, PNL y comunicación no violenta
- +13 años acompañando mujeres en sanación emocional y transformación personal
- Mamá de 5 hijos, emprendedora, experiencia personal con enfermedad crónica
- Instagram: @patygodinezcoach

AUDIENCIA: Mujeres 25-60 años que se sienten sobrepasadas emocionalmente, buscan sanar su relación consigo mismas.

TONO DE VOZ:
- Profundo, empático, humano
- Directo pero amoroso, sin juicio
- Con autoridad emocional (no arrogante)
- Esperanzador, íntimo, como hablar directo al alma
- Lenguaje claro, NO tecnicismos complicados

ESTILO DE COPY:
- Hooks emocionales fuertes al inicio
- Frases que confrontan con amor
- Preguntas que invitan a la introspección
- Cierre con reflexión profunda o CTA suave

PILARES: regulación emocional, autocompasión, neurociencia aplicada, sanación emocional, relaciones sanas, cuerpo/salud integral, mindfulness.

REGLA: Todo debe hacer sentir a la lectora: "Esto es exactamente lo que estoy viviendo… y sí hay una salida."

Responde SIEMPRE en español."""

CONTENT_PROMPT = """A partir de esta idea de Paty, genera contenido para publicar en Instagram y Facebook.

IDEA DE PATY: {idea}

Responde ÚNICAMENTE con un JSON válido, sin markdown ni backticks:
{{"caption": "Caption completo (150-250 palabras). Hook emocional fuerte, desarrollo profundo, CTA suave. Cierra con 5-8 hashtags del nicho.", "frase_imagen": "Frase corta y poderosa para la imagen, máximo 12 palabras. Impactante y memorable.", "categoria": "Una de: reflexion, pregunta, consejo, frase, motivacion"}}"""


# ══════════════════════════════════════════════════════════════════════
#  SEGURIDAD
# ══════════════════════════════════════════════════════════════════════

def es_paty(update: Update) -> bool:
    """Solo permite uso a Paty (o a todos si PATY_CHAT_ID no está definido)."""
    if not PATY_CHAT_ID:
        return True
    uid = update.effective_user.id if update.effective_user else None
    return str(uid) == str(PATY_CHAT_ID)


# ══════════════════════════════════════════════════════════════════════
#  MOTOR IA HÍBRIDO — OpenRouter (primary) + Groq (fallback)
# ══════════════════════════════════════════════════════════════════════

def _call_openrouter(messages: list, max_tokens: int = 1500, temperature: float = 0.7) -> str:
    """Llama a OpenRouter API (compatible con formato OpenAI)."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY no configurada")

    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/pipsgdl/lavozdelalma-bot",
            "X-Title": "La Voz del Alma Bot",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    return data["choices"][0]["message"]["content"].strip()


def _call_groq(messages: list, max_tokens: int = 1500, temperature: float = 0.7) -> str:
    """Llama a Groq API."""
    resp = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


def chat_ia(messages: list, max_tokens: int = 1500, temperature: float = 0.7) -> str:
    """Motor híbrido: intenta OpenRouter primero, Groq como fallback."""
    # Intento 1: OpenRouter (deepseek-chat-v3 gratis)
    if OPENROUTER_API_KEY:
        try:
            result = _call_openrouter(messages, max_tokens, temperature)
            logger.info("IA respondió vía OpenRouter (%s)", OPENROUTER_MODEL)
            return result
        except Exception as e:
            logger.warning("OpenRouter falló (%s), intentando Groq...", e)

    # Intento 2: Groq (LLaMA 3.3)
    try:
        result = _call_groq(messages, max_tokens, temperature)
        logger.info("IA respondió vía Groq (%s)", GROQ_MODEL)
        return result
    except Exception as e:
        logger.error("Groq también falló: %s", e)
        raise RuntimeError(f"Ambos motores IA fallaron. OpenRouter + Groq no disponibles: {e}")


def _parse_json_response(raw: str) -> dict:
    """Parsea JSON de una respuesta de LLM, limpiando markdown."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"No se pudo parsear respuesta del LLM: {raw[:300]}")


def generar_contenido(idea: str) -> dict:
    """Genera caption + frase para imagen desde una idea."""
    raw = chat_ia([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": CONTENT_PROMPT.format(idea=idea)},
    ])
    return _parse_json_response(raw)


AJUSTE_PROMPT = """Paty está iterando sobre un diseño de post. Te dice cómo ajustarlo.

ESTADO ACTUAL:
- Frase en la imagen: "{frase}"
- Template actual: {template}

TEMPLATES DISPONIBLES (nombre → descripción):
- crema → fondo beige muy claro, texto verde oscuro (tono suave, luminoso)
- bosque → fondo verde oscuro, texto crema (tono profundo, sereno)
- terracota → fondo cobre/tierra, texto crema (cálido, fuerte)
- lavanda → fondo rosa pálido, texto verde oscuro (delicado, claro)
- salvia → fondo verde salvia medio, texto crema (natural, equilibrado)

INSTRUCCIÓN DE PATY: "{instruccion}"

Interpreta lo que pide y devuelve SOLO JSON:
{{
  "frase": "nueva frase exacta o null si no cambia",
  "template": "nombre-del-template o null si no cambia",
  "cambio_resumido": "breve descripción del cambio en español (máx 10 palabras)"
}}

REGLAS DE INTERPRETACIÓN:
- "más claro / clarito / suave / luminoso" → crema o lavanda
- "más oscuro / fuerte / profundo" → bosque
- "cálido / tierra / cobre" → terracota
- "natural / verde" → salvia
- "rosa / delicado" → lavanda
- "edita la frase: X" / "cambia texto a X" / "pon X" → frase = X (usa el texto literal)
- Si solo cambia el fondo/color → frase = null
- Si solo cambia el texto → template = null
- Si pide ambas → devuelve ambas
- Si no entiendes → todos null y explica en cambio_resumido

Responde SOLO el JSON."""


def interpretar_ajuste(instruccion: str, frase: str, template_name: str) -> dict:
    """Interpreta una instrucción de ajuste con la IA."""
    raw = chat_ia(
        [{"role": "user", "content": AJUSTE_PROMPT.format(
            frase=frase, template=template_name, instruccion=instruccion,
        )}],
        max_tokens=300,
        temperature=0.2,
    )
    return _parse_json_response(raw)


def preguntar_ia(mensaje: str) -> str:
    """Respuesta libre con el motor IA híbrido."""
    return chat_ia([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": mensaje},
    ], max_tokens=1024)


async def transcribir_audio(file_path: str) -> str:
    """Transcribe audio con Whisper vía Groq (único servicio con Whisper gratis)."""
    with open(file_path, "rb") as f:
        t = groq_client.audio.transcriptions.create(
            file=(os.path.basename(file_path), f),
            model="whisper-large-v3-turbo",
            language="es",
        )
    return t.text.strip()


# ══════════════════════════════════════════════════════════════════════
#  GENERACIÓN DE IMÁGENES CON PILLOW
# ══════════════════════════════════════════════════════════════════════

def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def draw_sparkle(draw: ImageDraw.Draw, x: int, y: int, size: int, color):
    """Dibuja un destello / estrella de 4 puntas (signature de la marca)."""
    s6 = max(size // 6, 1)
    draw.polygon([(x, y - size), (x - s6, y), (x, y + size), (x + s6, y)], fill=color)
    draw.polygon([(x - size, y), (x, y - s6), (x + size, y), (x, y + s6)], fill=color)


def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Carga fuente con fallback a DejaVu Sans → default."""
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        logger.warning(f"Fuente no encontrada: {path}")
        for fallback in [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            try:
                return ImageFont.truetype(fallback, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Divide texto en líneas que caben en max_width píxeles."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generar_imagen(frase: str, template_idx: int | None = None) -> bytes:
    """Genera imagen de marca 1080×1080 con la frase dada."""
    W, H = 1080, 1080
    PAD  = 120

    # Elegir plantilla
    tpl = TEMPLATES[template_idx] if template_idx is not None else random.choice(TEMPLATES)
    bg      = hex_to_rgb(tpl["bg"])
    txt_col = hex_to_rgb(tpl["text"])
    accent  = hex_to_rgb(tpl["accent"])

    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Fuentes
    font_main   = load_font(FONT_TITLE,  62)
    font_brand  = load_font(FONT_SCRIPT, 32)
    font_tag    = load_font(FONT_SCRIPT, 24)

    # ── Decoración superior ──
    y_top = 100
    draw.line([(PAD + 40, y_top), (W - PAD - 40, y_top)], fill=accent, width=1)
    draw_sparkle(draw, PAD + 20, y_top, 12, accent)
    draw_sparkle(draw, W - PAD - 20, y_top, 12, accent)
    draw_sparkle(draw, W // 2, 55, 8, accent)

    # ── Decoración inferior ──
    y_bot = H - 170
    draw.line([(PAD + 40, y_bot), (W - PAD - 40, y_bot)], fill=accent, width=1)
    draw_sparkle(draw, PAD + 20, y_bot, 12, accent)
    draw_sparkle(draw, W - PAD - 20, y_bot, 12, accent)

    # ── Texto principal ──
    max_w = W - PAD * 2 - 40
    lines = wrap_text(frase, font_main, max_w, draw)

    line_h = 82
    total_h = len(lines) * line_h
    zone = y_bot - y_top - 40
    start_y = y_top + 20 + (zone - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        lw   = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, start_y + i * line_h), line, fill=txt_col, font=font_main)

    # ── Marca de agua ──
    brand = "Paty Godínez"
    bb = draw.textbbox((0, 0), brand, font=font_brand)
    bw = bb[2] - bb[0]
    draw.text(((W - bw) // 2, H - 135), brand, fill=accent, font=font_brand)

    tag = "La Voz del Alma"
    bt = draw.textbbox((0, 0), tag, font=font_tag)
    tw = bt[2] - bt[0]
    draw.text(((W - tw) // 2, H - 95), tag, fill=accent, font=font_tag)

    draw_sparkle(draw, W // 2 - bw // 2 - 22, H - 120, 6, accent)
    draw_sparkle(draw, W // 2 + bw // 2 + 22, H - 120, 6, accent)

    # Exportar
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════
#  SUBIDA DE IMÁGENES (imgbb)
# ══════════════════════════════════════════════════════════════════════

def subir_imagen(image_bytes: bytes) -> str:
    """Sube imagen a imgbb y devuelve URL pública."""
    if not IMGBB_API_KEY:
        raise RuntimeError(
            "IMGBB_API_KEY no configurada. Obtén una gratis en https://api.imgbb.com/"
        )
    data = urllib.parse.urlencode({
        "key":   IMGBB_API_KEY,
        "image": base64.b64encode(image_bytes).decode(),
        "name":  f"lavoz_{random.randint(1000, 9999)}",
    }).encode()
    req = urllib.request.Request("https://api.imgbb.com/1/upload", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"imgbb {e.code}: {body}") from None
    if not result.get("success"):
        raise RuntimeError(f"imgbb error: {result.get('error', result)}")
    return result["data"]["url"]


# ══════════════════════════════════════════════════════════════════════
#  META API  — Instagram + Facebook
# ══════════════════════════════════════════════════════════════════════

def meta_post(url: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body).get("error", {})
            msg  = err.get("error_user_msg") or err.get("message") or body
            code = err.get("code", e.code)
            sub  = err.get("error_subcode")
            extra = f" [subcode {sub}]" if sub else ""
            raise RuntimeError(f"Meta {e.code} (code {code}){extra}: {msg}") from None
        except (json.JSONDecodeError, AttributeError):
            raise RuntimeError(f"Meta {e.code}: {body[:300]}") from None


def publicar_instagram(image_url: str, caption: str) -> str:
    base = f"https://graph.instagram.com/v21.0/{IG_USER_ID}"
    r1 = meta_post(f"{base}/media", {
        "image_url": image_url, "caption": caption, "access_token": IG_TOKEN,
    })
    if "id" not in r1:
        raise RuntimeError(r1.get("error", {}).get("message", str(r1)))
    r2 = meta_post(f"{base}/media_publish", {
        "creation_id": r1["id"], "access_token": IG_TOKEN,
    })
    if "id" not in r2:
        raise RuntimeError(r2.get("error", {}).get("message", str(r2)))
    return r2["id"]


def publicar_facebook(image_url: str, caption: str) -> str:
    r = meta_post(f"https://graph.facebook.com/v21.0/{FB_PAGE_ID}/photos", {
        "url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN,
    })
    if "id" not in r:
        raise RuntimeError(r.get("error", {}).get("message", str(r)))
    return r["id"]


# ══════════════════════════════════════════════════════════════════════
#  TECLADO DE APROBACIÓN
# ══════════════════════════════════════════════════════════════════════

def teclado_preview() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publicar",       callback_data="pub_aprobar"),
            InlineKeyboardButton("🎨 Ajustar diseño", callback_data="pub_ajustar"),
        ],
        [
            InlineKeyboardButton("✏️ Editar caption", callback_data="pub_editar"),
            InlineKeyboardButton("🔄 Otra imagen",    callback_data="pub_regenerar"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="pub_cancelar"),
        ],
    ])


# ══════════════════════════════════════════════════════════════════════
#  PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════

async def pipeline_contenido(update: Update, ctx: ContextTypes.DEFAULT_TYPE, idea: str):
    """Idea → contenido IA → imagen de marca → preview con botones."""
    msg = await update.message.reply_text("🧠 Procesando tu idea...")

    try:
        # 1 — Generar caption + frase
        await msg.edit_text("✨ Generando caption y frase para la imagen...")
        contenido = generar_contenido(idea)
        caption  = contenido["caption"]
        frase    = contenido["frase_imagen"]
        cat      = contenido.get("categoria", "reflexion")

        # 2 — Generar imagen de marca
        await msg.edit_text("🎨 Creando diseño con la identidad de marca...")
        tpl_idx   = random.randrange(len(TEMPLATES))
        img_bytes = generar_imagen(frase, tpl_idx)

        # 3 — Guardar en estado
        ctx.user_data["pending"] = {
            "idea":          idea,
            "caption":       caption,
            "frase":         frase,
            "categoria":     cat,
            "image_bytes":   img_bytes,
            "template_idx":  tpl_idx,
            "template_name": TEMPLATES[tpl_idx]["name"],
        }

        # 4 — Preview
        await msg.delete()

        preview_caption = caption
        if len(preview_caption) > 950:
            preview_caption = preview_caption[:947] + "..."

        await update.message.reply_photo(
            photo=img_bytes,
            caption=f"📝 *Preview del post:*\n\n{preview_caption}",
            parse_mode="Markdown",
            reply_markup=teclado_preview(),
        )

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        await msg.edit_text(
            f"❌ Error generando contenido: {e}\n\nIntenta de nuevo con otra idea."
        )


# ══════════════════════════════════════════════════════════════════════
#  COMANDOS
# ══════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text(
        "✨ *Hola Paty* — Soy tu asistente de La Voz del Alma v3.0\n\n"
        "Ahora funciono así:\n\n"
        "1️⃣ Mándame una *idea* (texto o audio)\n"
        "2️⃣ Yo genero el *caption + imagen* de marca\n"
        "3️⃣ Te muestro un *preview*\n"
        "4️⃣ Tú *apruebas* y publico en IG + FB\n\n"
        "También puedes:\n"
        "📸 Mandar una *foto* con texto → uso tu foto + genero caption\n"
        "💡 /ideas — 5 ideas de contenido\n"
        "📋 /estado — Ver post pendiente\n"
        "❓ /ayuda — Todos los comandos\n\n"
        "💡 *Solo mándame tu idea y yo me encargo del resto*",
        parse_mode="Markdown",
    )


async def cmd_ideas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text("💡 Generando ideas para hoy...")
    try:
        ideas = preguntar_ia(
            "Dame 5 ideas de contenido originales para hoy en Instagram. "
            "Para cada una incluye: formato (reel/carrusel/post), hook inicial "
            "y por qué conectaría con la audiencia."
        )
        await update.message.reply_text(ideas)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    p = ctx.user_data.get("pending")
    if p:
        await update.message.reply_text(
            f"📋 *Post pendiente:*\n\n"
            f"💡 Idea: _{p['idea'][:120]}_\n"
            f"🏷 Categoría: {p['categoria']}\n\n"
            "Usa los botones del preview para publicar o cancelar.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "No hay publicaciones pendientes. ¡Mándame una idea! 💡"
        )


async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text(
        "🌿 *La Voz del Alma — Comandos*\n\n"
        "💬 Escribe una *idea* → genero caption + imagen + preview\n"
        "🎙 Manda un *audio* → transcribo y proceso\n"
        "📸 Manda una *foto con texto* → uso tu foto + genero caption\n\n"
        "/ideas — 5 ideas de contenido para hoy\n"
        "/estado — Ver post pendiente\n"
        "/ayuda — Este menú\n\n"
        "En el preview puedes:\n"
        "✅ Publicar en IG + FB\n"
        "✏️ Editar el caption\n"
        "🎨 Generar otra imagen\n"
        "❌ Cancelar",
        parse_mode="Markdown",
    )


# ══════════════════════════════════════════════════════════════════════
#  HANDLERS DE MENSAJES
# ══════════════════════════════════════════════════════════════════════

async def handle_texto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    texto = update.message.text.strip()

    # ¿Está editando caption?
    if ctx.user_data.get("editing_caption"):
        ctx.user_data["editing_caption"] = False
        p = ctx.user_data.get("pending")
        if p:
            p["caption"] = texto
            preview = texto if len(texto) <= 950 else texto[:947] + "..."
            await update.message.reply_photo(
                photo=p["image_bytes"],
                caption=f"📝 *Caption actualizado:*\n\n{preview}",
                parse_mode="Markdown",
                reply_markup=teclado_preview(),
            )
            return

    # ¿Está en modo ajuste de diseño?
    if ctx.user_data.get("editing_design"):
        p = ctx.user_data.get("pending")
        if not p:
            ctx.user_data["editing_design"] = False
            await update.message.reply_text(
                "⚠️ No hay post activo. Mándame una idea nueva para empezar."
            )
            return

        if texto.lower() in {"listo", "ok", "salir", "/listo", "fin", "ya"}:
            ctx.user_data["editing_design"] = False
            await update.message.reply_photo(
                photo=p["image_bytes"],
                caption=(
                    f"✨ *Diseño final* (_{p.get('template_name', 'N/A')}_)\n\n"
                    f"{p['caption'][:900]}"
                ),
                parse_mode="Markdown",
                reply_markup=teclado_preview(),
            )
            return

        msg = await update.message.reply_text("🎨 Aplicando ajuste...")
        try:
            ajuste = interpretar_ajuste(
                texto,
                p["frase"],
                p.get("template_name", "random"),
            )
        except Exception as e:
            logger.error(f"Interpretar ajuste falló: {e}", exc_info=True)
            await msg.edit_text(
                f"❌ No entendí el ajuste: {e}\n\nPrueba algo como _fondo más claro_ o _cambia la frase a 'soy refugio'_.",
                parse_mode="Markdown",
            )
            return

        nueva_frase    = ajuste.get("frase") or p["frase"]
        nuevo_tpl_name = ajuste.get("template") or p.get("template_name")
        resumen        = ajuste.get("cambio_resumido", "ajuste aplicado")

        tpl_idx = next(
            (i for i, t in enumerate(TEMPLATES) if t["name"] == nuevo_tpl_name),
            p.get("template_idx", 0),
        )

        try:
            new_img = generar_imagen(nueva_frase, tpl_idx)
        except Exception as e:
            await msg.edit_text(f"❌ Error generando imagen: {e}")
            return

        p["frase"]         = nueva_frase
        p["image_bytes"]   = new_img
        p["template_idx"]  = tpl_idx
        p["template_name"] = TEMPLATES[tpl_idx]["name"]

        await msg.delete()
        preview = p["caption"] if len(p["caption"]) <= 900 else p["caption"][:897] + "..."
        await update.message.reply_photo(
            photo=new_img,
            caption=(
                f"🎨 *{resumen}*\n"
                f"_Template: {p['template_name']}_\n\n"
                f"{preview}\n\n"
                "_Sigue ajustando o escribe_ *listo* _para terminar._"
            ),
            parse_mode="Markdown",
            reply_markup=teclado_preview(),
        )
        return

    # Pipeline normal: tratar como nueva idea
    await pipeline_contenido(update, ctx, texto)


async def handle_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not es_paty(update):
        return
    await update.message.reply_text("🎙 Transcribiendo tu audio...")
    try:
        voice   = update.message.voice or update.message.audio
        tg_file = await voice.get_file()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await tg_file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        texto = await transcribir_audio(tmp_path)
        os.unlink(tmp_path)

        await update.message.reply_text(
            f"📝 *Transcripción:*\n_{texto}_", parse_mode="Markdown"
        )

        # Procesar como idea
        await pipeline_contenido(update, ctx, texto)

    except Exception as e:
        logger.error(f"Audio error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error al procesar audio: {e}")


async def handle_foto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Paty manda foto → usa esa imagen + genera caption."""
    if not es_paty(update):
        return

    idea = update.message.caption or ""
    if not idea:
        await update.message.reply_text(
            "📸 Recibí tu foto. Mándala de nuevo con un texto en el caption "
            "describiendo la idea del post."
        )
        return

    await update.message.reply_text("✨ Generando caption para tu foto...")
    try:
        photo   = update.message.photo[-1]
        tg_file = await photo.get_file()

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await tg_file.download_to_drive(tmp.name)
            with open(tmp.name, "rb") as f:
                photo_bytes = f.read()
            os.unlink(tmp.name)

        contenido = generar_contenido(idea)

        ctx.user_data["pending"] = {
            "idea":        idea,
            "caption":     contenido["caption"],
            "frase":       idea,
            "categoria":   contenido.get("categoria", "reflexion"),
            "image_bytes": photo_bytes,
            "is_photo":    True,
        }

        preview = contenido["caption"]
        if len(preview) > 950:
            preview = preview[:947] + "..."

        await update.message.reply_photo(
            photo=photo_bytes,
            caption=f"📝 *Preview del post:*\n\n{preview}",
            parse_mode="Markdown",
            reply_markup=teclado_preview(),
        )

    except Exception as e:
        logger.error(f"Foto error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


# ══════════════════════════════════════════════════════════════════════
#  CALLBACKS (BOTONES INLINE)
# ══════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not es_paty(update):
        return

    p = ctx.user_data.get("pending")
    if not p:
        await query.edit_message_caption(
            "⚠️ No hay post pendiente. Mándame una nueva idea."
        )
        return

    action = query.data

    # ── APROBAR → Publicar ──────────────────────────────────────────
    if action == "pub_aprobar":
        ctx.user_data.pop("editing_design", None)
        ctx.user_data.pop("editing_caption", None)
        await query.edit_message_caption(
            "📤 *Subiendo imagen y publicando...*", parse_mode="Markdown"
        )
        try:
            image_url  = subir_imagen(p["image_bytes"])
            caption    = p["caption"]
            resultados = []

            try:
                publicar_instagram(image_url, caption)
                resultados.append("✅ *Instagram* — ¡Publicado!")
            except Exception as e:
                resultados.append(f"❌ *Instagram* — {e}")

            try:
                publicar_facebook(image_url, caption)
                resultados.append("✅ *Facebook* — ¡Publicado!")
            except Exception as e:
                resultados.append(f"❌ *Facebook* — {e}")

            ctx.user_data.pop("pending", None)

            await query.edit_message_caption(
                "🎉 *Resultado:*\n\n"
                + "\n".join(resultados)
                + "\n\n💡 ¡Mándame otra idea cuando quieras!",
                parse_mode="Markdown",
            )

        except Exception as e:
            logger.error(f"Publish error: {e}", exc_info=True)
            await query.edit_message_caption(
                f"❌ Error al publicar: {e}\n\nIntenta de nuevo con ✅ Publicar.",
                parse_mode="Markdown",
                reply_markup=teclado_preview(),
            )

    # ── EDITAR caption ──────────────────────────────────────────────
    elif action == "pub_editar":
        ctx.user_data["editing_caption"] = True
        await query.edit_message_caption(
            "✏️ Escribe el nuevo caption y te muestro el preview actualizado:"
        )

    # ── REGENERAR imagen (rotando template) ─────────────────────────
    elif action == "pub_regenerar":
        await query.edit_message_caption("🎨 Generando nueva imagen...")
        try:
            current = p.get("template_idx", 0)
            new_idx = (current + random.randint(1, len(TEMPLATES) - 1)) % len(TEMPLATES)
            new_img = generar_imagen(p["frase"], new_idx)
            p["image_bytes"]   = new_img
            p["template_idx"]  = new_idx
            p["template_name"] = TEMPLATES[new_idx]["name"]

            preview = p["caption"]
            if len(preview) > 950:
                preview = preview[:947] + "..."

            await query.message.reply_photo(
                photo=new_img,
                caption=f"📝 *Preview actualizado* (_{TEMPLATES[new_idx]['name']}_):\n\n{preview}",
                parse_mode="Markdown",
                reply_markup=teclado_preview(),
            )
        except Exception as e:
            await query.edit_message_caption(
                f"❌ Error: {e}",
                reply_markup=teclado_preview(),
            )

    # ── AJUSTAR diseño (modo conversacional) ────────────────────────
    elif action == "pub_ajustar":
        ctx.user_data["editing_design"] = True
        await query.edit_message_caption(
            "🎨 *Modo ajuste de diseño activado*\n\n"
            "Escríbeme qué cambiar — ejemplos:\n"
            "• _fondo más claro_\n"
            "• _usa template bosque_\n"
            "• _edita la frase: soy mi refugio_\n"
            "• _cambia a terracota y pon 'respiro y vuelvo'_\n\n"
            f"🎨 Template actual: *{p.get('template_name', 'N/A')}*\n"
            f"💬 Frase actual: _{p['frase']}_\n\n"
            "Cuando termines, escribe *listo* o toca ✅ Publicar en el siguiente preview.",
            parse_mode="Markdown",
        )

    # ── CANCELAR ────────────────────────────────────────────────────
    elif action == "pub_cancelar":
        ctx.user_data.pop("pending", None)
        ctx.user_data.pop("editing_caption", None)
        ctx.user_data.pop("editing_design", None)
        await query.edit_message_caption(
            "🚫 Publicación cancelada.\n💡 ¡Mándame otra idea cuando quieras!"
        )


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("ideas",  cmd_ideas))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("ayuda",  cmd_ayuda))
    app.add_handler(CommandHandler("help",   cmd_ayuda))

    # Callbacks (botones inline)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Mensajes
    app.add_handler(MessageHandler(filters.PHOTO, handle_foto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))

    logger.info("🤖 Bot La Voz del Alma v3.0 iniciado")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
