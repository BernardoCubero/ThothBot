#!/bin/bash
# ============================================================
# ThothBot - Guardián Automático (Watchdog)
# Este script verifica la salud de ThothBot y lo levanta
# automáticamente en caso de cuelgue o caída.
# ============================================================

PATH_BOT="/home/bernie/ThothBot"
LOG_FILE="/home/bernie/ThothBot/watchdog.log"
DATE=$(date "+%Y-%m-%d %H:%M:%S")

# Asegurarse de entrar al directorio correcto
cd "$PATH_BOT" || exit 1

# Comprobar si Docker daemon está respondiendo
if ! systemctl is-active --quiet docker; then
    echo "[$DATE] ERROR: El servicio Docker del sistema está caído. Iniciándolo..." >> "$LOG_FILE"
    sudo systemctl start docker
    sleep 5
fi

# 1. Comprobar si los contenedores esenciales están en estado "Running"
CONTAINERS_DOWN=0
for container in thothbot-rasa thothbot-telegram thothbot-actions; do
    STATUS=$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null)
    if [ "$STATUS" != "true" ]; then
        echo "[$DATE] ALERTA: Contenedor $container fuera de servicio." >> "$LOG_FILE"
        CONTAINERS_DOWN=1
    fi
done

# 2. Comprobar si el motor de Rasa responde en su puerto (5005)
# Si está colgado internamente (aunque el contenedor salga "Up"), la API dará timeout.
RASA_RESPONDING=0
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 8 http://127.0.0.1:5005/)
# Rasa suele devolver 200 (Hello) o 405 (Method not allowed) en la raíz. Ambas indican que el proceso está vivo.
if [ "$HTTP_STATUS" -eq 200 ] || [ "$HTTP_STATUS" -eq 405 ] || [ "$HTTP_STATUS" -eq 404 ]; then
    RASA_RESPONDING=1
fi

# 2.5 Comprobar si hay un conflicto de token en los logs de Telegram
TELEGRAM_CONFLICT=0
if docker compose logs --tail=25 telegram_proxy 2>/dev/null | grep -q "Conflict"; then
    echo "[$DATE] ALERTA: Conflicto detectado en la API de Telegram (Token duplicado)." >> "$LOG_FILE"
    TELEGRAM_CONFLICT=1
fi

# 3. Aplicar autorrecuperación en caso de fallo crítico o conflicto de API
if [ "$CONTAINERS_DOWN" -eq 1 ] || [ "$RASA_RESPONDING" -eq 0 ] || [ "$TELEGRAM_CONFLICT" -eq 1 ]; then
    echo "[$DATE] [AUTOCURACIÓN] Fallo de salud detectado. Reiniciando bot..." >> "$LOG_FILE"
    
    # 3.1 Evitar conflictos eliminando posibles webhooks remotos duplicados
    if [ -f .env ]; then
        TOKEN=$(grep TOKEN_TELEGRAM .env | cut -d= -f2 | tr -d '"' | tr -d ' ')
        if [ ! -z "$TOKEN" ]; then
            curl -s -X POST "https://api.telegram.org/bot${TOKEN}/deleteWebhook?drop_pending_updates=true" > /dev/null 2>&1
        fi
    fi
    
    # 3.2 Reiniciar el ecosistema Docker de raíz
    docker compose down >> "$LOG_FILE" 2>&1
    sleep 2
    docker compose up -d >> "$LOG_FILE" 2>&1
    
    echo "[$DATE] [AUTOCURACIÓN] Bot reiniciado correctamente." >> "$LOG_FILE"
else
    # Opcional: Solo registrar señal de vida cada hora para evitar logs gigantescos
    MINUTES=$(date "+%M")
    if [ "$MINUTES" = "00" ] || [ "$MINUTES" = "30" ]; then
        echo "[$DATE] Latido del sistema: Todo correcto y respondiendo." >> "$LOG_FILE"
    fi
fi
