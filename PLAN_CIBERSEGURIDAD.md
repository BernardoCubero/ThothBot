# Plan de Ciberseguridad y Bastionado (Hardening) de ThothBot

Este documento recoge el análisis del incidente de seguridad detectado el **21 de mayo de 2026**, las medidas técnicas inmediatas implementadas para mitigar el ataque y blindar la infraestructura en producción, y las buenas prácticas aplicadas de cara a la defensa del **Trabajo Fin de Grado (TFG)**.

---

## 1. Análisis del Incidente de Seguridad (Ransomware)

### 🔍 El Problema Original
Durante la auditoría del sistema ThothBot en producción en el VPS (`135.125.101.196`), se detectó que el bot había dejado de responder. El análisis de logs reveló un error crítico: `Unknown database 'thothbot_db'`.

Al acceder al motor de bases de datos, se descubrió que:
* **MariaDB** había sido vulnerada. Todas las tablas legítimas fueron eliminadas y se había creado una base de datos maliciosa llamada `RECOVER_YOUR_DATA`.
* **MongoDB** también fue comprometida, creándose una colección llamada `READ_ME_TO_RECOVER_YOUR_DATA`.
* El atacante dejó la siguiente nota de rescate en formato binario/tabla exigiendo el pago de criptomonedas (Bitcoin):
  > *"All your data was backed up by us. You must pay 0.0109 bitcoin to [...] or in 48 hours, your data will be publicly disclosed and deleted..."*

### 🔓 Vector de Ataque Utilizado
El ataque fue perpetrado por un bot automático de escaneo de internet debido a dos vulnerabilidades principales en la configuración de la infraestructura:
1. **Exposición de Puertos de Bases de Datos:** En el archivo `docker-compose.yml`, los puertos de MariaDB (`3307:3306`) y MongoDB (`27018:27017`) estaban expuestos públicamente al tráfico de internet en el VPS.
2. **Credenciales Débiles:** La contraseña de administración del usuario `root` de MariaDB estaba configurada por defecto como `1234` en el archivo `.env`.

---

## 2. Medidas de Mitigación y Blindaje Aplicadas

Para neutralizar la amenaza de forma inmediata y garantizar la máxima seguridad en producción, se han implementado las siguientes mejoras de bastionado (*hardening*):

### Capa 1: Aislamiento Total de Red (Zero Trust)
Las bases de datos relacionales y NoSQL de ThothBot no requieren visibilidad externa en internet, ya que toda la interacción de datos ocurre de manera interna entre contenedores dentro de la red privada de Docker (`thothbot-net`).

* **Acción realizada:** Se han comentado y deshabilitado por completo los mapeos de puertos públicos en `docker-compose.yml`:
  ```yaml
    # MariaDB
    # ports:
    #   - "127.0.0.1:3307:3306" # Comentado por ciberseguridad: Aislamiento total de red
  
    # MongoDB
    # ports:
    #   - "127.0.0.1:27018:27017" # Comentado por ciberseguridad: Aislamiento total de red
  ```
* **Resultado:** Las bases de datos ahora son invisibles e inaccesibles desde internet pública. Solo los contenedores autorizados (`action_server` y `rasa`) en la misma red virtual pueden comunicarse con ellas.

### Capa 2: Robustez en la Gestión de Conexiones (SQLAlchemy)
Para evitar el error de inactividad `MySQL server has gone away` (causado cuando MariaDB desconecta conexiones inactivas tras varias horas de desuso), se han añadido parámetros de resiliencia al motor de SQLAlchemy en `database/connection.py`:
```python
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    pool_recycle=3600,   # Recicla conexiones viejas cada hora (evita hilos colgados)
    pool_pre_ping=True   # Valida la conexión antes de entregarla para evitar Broken Pipes
)
```

### Capa 3: Criptografía y Fortalecimiento de Credenciales
* **Acción realizada:** Se modificó la contraseña original de la base de datos de `1234` a una contraseña de alta seguridad criptográfica: `ThothSecure_MariaDB_2026_TFG!`.
* **Aplicación:** Se forzó la actualización del usuario de MariaDB en producción utilizando privilegios locales de administración en el contenedor:
  ```sql
  ALTER USER 'root'@'%' IDENTIFIED BY 'ThothSecure_MariaDB_2026_TFG!';
  ALTER USER 'root'@'localhost' IDENTIFIED BY 'ThothSecure_MariaDB_2026_TFG!';
  FLUSH PRIVILEGES;
  ```
* **Resultado:** Se eliminó la vulnerabilidad de contraseña débil y se limpiaron por completo las bases de datos de secuestro creadas por el atacante.

### Capa 4: Seguridad de Ficheros y Permisos del Sistema
El archivo `.env` almacena credenciales altamente sensibles, tales como la clave del Bot de Telegram y las API Keys de Geoapify y Ticketmaster.
* **Acción realizada:** Se restringieron los permisos del archivo `.env` en el servidor VPS usando el sistema de permisos POSIX:
  ```bash
  chmod 600 ~/ThothBot/.env
  ```
* **Resultado:** Únicamente el usuario propietario (`bernie`) puede leer o escribir el archivo, impidiendo que otros procesos del sistema leyeren las claves secretas.

---

## 3. Recomendaciones y Siguientes Pasos (Para la memoria de TFG)

Como propuesta de mejora y buenas prácticas de seguridad para el futuro, se sugieren las siguientes implementaciones:

1. **Uso de Túneles SSH para Gestión Local:**
   Si en algún momento necesitas inspeccionar la base de datos usando una herramienta GUI externa (como DBeaver), no abras los puertos públicos en el VPS. En su lugar, realiza un **túnel SSH seguro** desde tu terminal local:
   ```bash
   ssh -L 3307:thothbot-mariadb:3306 -p 2224 bernie@135.125.101.196
   ```
   Esto te permitirá conectar DBeaver a `localhost:3307` de forma local, enrutando todo el tráfico de forma cifrada a través de tu conexión SSH privada.

2. **Hardening del Servidor SSH:**
   Deshabilita el inicio de sesión por contraseña en tu VPS (`/etc/ssh/sshd_config`) y permite únicamente la autenticación mediante claves criptográficas (`PasswordAuthentication no`, `PubkeyAuthentication yes`). Esto mitigará al 100% los ataques automatizados de fuerza bruta al puerto `2224`.

3. **Principio de Mínimo Privilegio en SQL:**
   En entornos de producción reales, la aplicación no debería conectar con el usuario `root`. Se recomienda crear un usuario específico (ej: `thothbot_app`) que solo tenga permisos `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre la base de datos `thothbot_db`, limitando el impacto de un potencial fallo en el código de la app.
