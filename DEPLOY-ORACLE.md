# Deploy en Oracle Cloud Always Free — La Voz del Alma Bot v3.0

## Requisitos previos
- Cuenta Oracle Cloud (gratis: cloud.oracle.com)
- API key de OpenRouter (gratis: openrouter.ai)
- API key de Groq (gratis: console.groq.com)
- API key de imgbb (gratis: api.imgbb.com)
- Credenciales de Meta API (ya las tienes)

---

## Paso 1 — Crear instancia Oracle Cloud (gratis para siempre)

1. Entra a **cloud.oracle.com** → Compute → Instances → Create Instance
2. Configuración:
   - **Shape:** VM.Standard.A1.Flex (ARM) — 1 OCPU, 6 GB RAM (gratis)
   - **Image:** Ubuntu 22.04 (Canonical)
   - **Network:** Crear VCN con subnet pública
   - **SSH Key:** Subir tu llave pública (~/.ssh/id_rsa.pub)
3. Clic en **Create** — espera ~2 minutos
4. Anota la **IP pública** de la instancia

---

## Paso 2 — Configurar el servidor

```bash
# Conectar por SSH
ssh ubuntu@<IP_PUBLICA>

# Actualizar el sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker + Docker Compose
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
# Cerrar y reconectar SSH para que tome efecto
exit
ssh ubuntu@<IP_PUBLICA>

# Instalar Git
sudo apt install -y git
```

---

## Paso 3 — Clonar el repo y configurar

```bash
# Clonar el repositorio
git clone https://github.com/pipsgdl/lavozdelalma-bot.git
cd lavozdelalma-bot

# Crear archivo .env con las credenciales reales
cp .env.example .env
nano .env
# Llenar TODAS las variables con valores reales
```

---

## Paso 4 — Iniciar el bot

```bash
# Construir y levantar con Docker Compose
docker compose up -d --build

# Verificar que está corriendo
docker compose logs -f

# El bot queda activo 24/7. Se reinicia solo si se cae (restart: always)
```

---

## Comandos útiles

```bash
# Ver logs en tiempo real
docker compose logs -f

# Reiniciar el bot
docker compose restart

# Actualizar el bot (cuando subas cambios a GitHub)
git pull && docker compose up -d --build

# Ver estado
docker compose ps

# Detener
docker compose down
```

---

## Paso 5 — Conectar Tailscale (opcional, recomendado)

Para acceder al servidor desde cualquier lugar sin exponer puertos:

```bash
# Instalar Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Autenticar con tu cuenta Tailscale
# Ahora puedes acceder por SSH via Tailscale IP
```

---

## Seguridad

- El archivo `.env` NO debe subirse a GitHub (ya está en .gitignore)
- Los tokens de Meta expiran cada ~60 días — renovar cuando fallen
- Oracle Cloud Always Free no tiene cargos si usas shapes elegibles
- El firewall de Oracle bloquea todo por default — no necesitas abrir puertos (el bot hace polling, no webhooks)

---

## Arquitectura v3.0

```
Paty (Telegram)
    ↓ texto / audio / foto
Bot Python (Oracle Cloud ARM)
    ↓ OpenRouter (deepseek-v3 gratis) → fallback Groq (LLaMA 3.3)
    ↓ Pillow (imagen de marca 1080x1080)
    ↓ imgbb (hosting imagen)
    ↓ Meta Graph API
Instagram + Facebook
```
