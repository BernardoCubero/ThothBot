#!/bin/bash
# ============================================================
# ThothBot - Script de Copia de Seguridad
# Uso: ./scripts/backup.sh
# Requiere acceso SSH al VPS configurado en REMOTE_HOST
# ============================================================

set -e

# ---- Configuración ----
REMOTE_HOST="135.125.101.196"
REMOTE_PORT="2224"
REMOTE_USER="bernie"
REMOTE_PATH="~/ThothBot"
LOCAL_BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="thothbot_backup_${DATE}"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}===============================${NC}"
echo -e "${GREEN}  ThothBot - Backup ${DATE}${NC}"
echo -e "${GREEN}===============================${NC}"

# Crear directorio de backup local
mkdir -p "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}"

# ---- 1. Backup de MariaDB ----
echo -e "\n${YELLOW}[1/4] Exportando base de datos MariaDB...${NC}"
ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \
  "cd ${REMOTE_PATH} && \
   DB_USER=\$(grep MARIADB_USER .env | cut -d= -f2) && \
   DB_PASS=\$(grep MARIADB_PASSWORD .env | cut -d= -f2) && \
   DB_NAME=\$(grep MARIADB_DB .env | cut -d= -f2) && \
   docker compose exec -T db mysqldump -u\${DB_USER} -p\${DB_PASS} \${DB_NAME}" \
  > "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/mariadb_dump.sql"

echo -e "  ✅ MariaDB → ${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/mariadb_dump.sql"

# ---- 2. Backup de archivos de configuración críticos ----
echo -e "\n${YELLOW}[2/4] Copiando archivos de configuración del VPS...${NC}"
scp -P ${REMOTE_PORT} -o StrictHostKeyChecking=no \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/credentials.yml" \
  "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/credentials.yml"

scp -P ${REMOTE_PORT} -o StrictHostKeyChecking=no \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/.env" \
  "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/.env"

echo -e "  ✅ credentials.yml y .env copiados"

# ---- 3. Backup de acciones (código Python) ----
echo -e "\n${YELLOW}[3/4] Comprimiendo código de acciones...${NC}"
tar -czf "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/actions.tar.gz" \
  ./actions/ \
  ./data/ \
  ./web_interface/ \
  ./telegram_proxy/ \
  ./services/ \
  ./models/ \
  ./domain.yml \
  ./config.yml \
  ./credentials.yml \
  2>/dev/null || true

echo -e "  ✅ Código comprimido en actions.tar.gz"

# ---- 4. Sincronizar configuración local → VPS ----
echo -e "\n${YELLOW}[4/4] Sincronizando archivos críticos local → VPS...${NC}"
scp -P ${REMOTE_PORT} -o StrictHostKeyChecking=no \
  ./credentials.yml \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/credentials.yml"

# Sincronizar actions y data (por si hay diferencias)
ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \
  "mkdir -p ${REMOTE_PATH}/actions ${REMOTE_PATH}/data"

rsync -avz -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
  ./actions/ \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/actions/" \
  --quiet

rsync -avz -e "ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no" \
  ./data/ \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/data/" \
  --quiet

echo -e "  ✅ credentials.yml, actions/ y data/ sincronizados con el VPS"

# ---- Resumen ----
echo -e "\n${GREEN}===============================${NC}"
echo -e "${GREEN}  Backup completado${NC}"
echo -e "${GREEN}  Guardado en: ${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/${NC}"
echo -e "${GREEN}===============================${NC}"
ls -lh "${LOCAL_BACKUP_DIR}/${BACKUP_NAME}/"
