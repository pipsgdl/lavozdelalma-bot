# Bot de Telegram — La Voz del Alma v2.0

**Flujo automático:** Idea → Caption + Imagen de marca → Preview → Aprobación → Publicación en IG + FB

Motor IA: **Groq** (LLaMA 3.3 + Whisper) — gratis  
Imágenes: **Pillow** con fuentes y colores oficiales de la marca  
Hosting imágenes: **imgbb** — gratis  
Deploy: **Railway** — 24/7

## Archivos

```
telegram-bot/
├── bot.py              ← Bot principal v2.0
├── requirements.txt    ← Dependencias Python
├── Procfile            ← Comando de inicio para Railway
├── fonts/
│   ├── bruney-season.otf    ← Tipografía principal de la marca
│   └── New-Icon-Script.otf  ← Tipografía de firma/taglines
├── .env.example        ← Plantilla de variables
└── .env.railway        ← Variables reales (NO subir a GitHub público)
```

## Flujo de uso

1. Paty manda una **idea** por texto o audio al bot de Telegram
2. El bot **transcribe** el audio (si aplica) con Whisper/Groq
3. Genera un **caption profesional** alineado con la voz de la marca
4. Crea una **imagen de marca** (1080×1080) con la paleta y tipografías oficiales
5. Muestra un **preview** con botones:
   - ✅ **Publicar** → sube a imgbb → publica en Instagram + Facebook
   - ✏️ **Editar caption** → Paty escribe nuevo texto → actualiza preview
   - 🎨 **Otra imagen** → genera nuevo diseño con diferente plantilla
   - ❌ **Cancelar** → descarta la publicación
6. También acepta **fotos** de Paty como imagen del post

## Comandos

| Comando | Función |
|---|---|
| `/start` | Mensaje de bienvenida |
| `/ideas` | 5 ideas de contenido para hoy |
| `/estado` | Ver si hay un post pendiente |
| `/ayuda` | Lista de comandos |

## Variables de entorno

| Variable | Dónde obtenerla |
|---|---|
| `TELEGRAM_TOKEN` | @BotFather en Telegram |
| `PATY_CHAT_ID` | @userinfobot en Telegram |
| `GROQ_API_KEY` | console.groq.com |
| `IG_USER_ID` | Ya configurado: 17841480108554471 |
| `IG_TOKEN` | Dashboard de Meta Developers |
| `FB_PAGE_ID` | Ya configurado: 892387700633150 |
| `FB_PAGE_TOKEN` | Graph API Explorer |
| `IMGBB_API_KEY` | https://api.imgbb.com/ (crear cuenta gratis) |

## Deploy / Actualización en Railway

1. Sube los archivos actualizados a GitHub (incluyendo carpeta fonts/)
2. Railway detecta el cambio y redeploya automáticamente
3. Agrega `IMGBB_API_KEY` en Railway → Variables (nueva en v2.0)
