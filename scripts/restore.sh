#!/bin/bash
# ============================================================
# ThothBot - Script de Restauración
# Uso: ./scripts/restore.sh backups/thothbot_backup_YYYYMMDD_HHMMSS
# ============================================================

set -e

REMOTE_HOST="135.125.101.196"
REMOTE_PORT="2224"
REMOTE_USER="bernie"
REMOTE_PATH="~/ThothBot"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Verificar argumento
if [ -z "$1" ]; then
  echo -e "${RED}Error: especifica la carpeta de backup.${NC}"
  echo "Uso: ./scripts/restore.sh backups/thothbot_backup_YYYYMMDD_HHMMSS"
  echo ""
  echo "Backups disponibles:"
  ls -1 ./backups/ 2>/dev/null || echo "(ninguno)"
  exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "${BACKUP_DIR}" ]; then
  echo -e "${RED}Error: directorio de backup no encontrado: ${BACKUP_DIR}${NC}"
  exit 1
fi

echo -e "${GREEN}===============================${NC}"
echo -e "${GREEN}  ThothBot - Restauración${NC}"
echo -e "${GREEN}  Backup: ${BACKUP_DIR}${NC}"
echo -e "${GREEN}===============================${NC}"

# ---- 1. Restaurar MariaDB ----
if [ -f "${BACKUP_DIR}/mariadb_dump.sql" ]; then
  echo -e "\n${YELLOW}[1/3] Restaurando base de datos MariaDB...${NC}"
  ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \
    "cd ${REMOTE_PATH} && \
     DB_USER=\$(grep MARIADB_USER .env | cut -d= -f2) && \
     DB_PASS=\$(grep MARIADB_PASSWORD .env | cut -d= -f2) && \
     DB_NAME=\$(grep MARIADB_DB .env | cut -d= -f2) && \
     docker compose exec -T db mysql -u\${DB_USER} -p\${DB_PASS} \${DB_NAME}" \
    < "${BACKUP_DIR}/mariadb_dump.sql"
  echo -e "  ✅ MariaDB restaurada"
else
  echo -e "  ⚠️  No hay dump de MariaDB en este backup"
fi

# ---- 2. Restaurar credentials.yml ----
if [ -f "${BACKUP_DIR}/credentials.yml" ]; then
  echo -e "\n${YELLOW}[2/3] Restaurando credentials.yml en VPS...${NC}"
  scp -P ${REMOTE_PORT} -o StrictHostKeyChecking=no \
    "${BACKUP_DIR}/credentials.yml" \
    "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/credentials.yml"
  echo -e "  ✅ credentials.yml restaurado"
fi

# ---- 3. Reiniciar contenedores ----
echo -e "\n${YELLOW}[3/3] Reiniciando contenedores en el VPS...${NC}"
ssh -p ${REMOTE_PORT} -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} \
  "cd ${REMOTE_PATH} && docker compose restart rasa action_server"
echo -e "  ✅ Contenedores reiniciados"

echo -e "\n${GREEN}===============================${NC}"
echo -e "${GREEN}  Restauración completada${NC}"
echo -e "${GREEN}===============================${NC}"
