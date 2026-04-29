# Manual de Base de Datos — ThothBot

Referencia técnica del sistema de persistencia de usuarios con MariaDB y SQLAlchemy ORM.

---

## Estructura de archivos implicados

```
ThothBot/
├── .env                        ← credenciales (nunca subir a git)
├── models/
│   └── usuario.py              ← definición de la tabla (ORM)
├── database/
│   ├── connection.py           ← engine y sesión compartidos
│   └── setup_db.py             ← script de inicialización (ejecutar 1 vez)
└── services/
    └── user_service.py         ← lógica: guardar_usuario / buscar_usuario
```

---

## Variables de entorno (`.env`)

```env
MARIADB_USER=root
MARIADB_PASSWORD=tu_contraseña
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_DB=thothbot_db
```

> **Nota:** `os.getenv("MARIADB_USER")` lee directamente esta variable.
> Si la variable no está definida devuelve `None`.
> Si pones `os.getenv("MARIADB_USER", "root")` el `"root"` es un valor
> de reserva que solo se usa si la variable NO existe en el `.env`.

---

## `models/usuario.py` — El modelo ORM

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(255), nullable=False, unique=True)
    nombre          = Column(String(100))
    ciudad_origen   = Column(String(100))
    pais            = Column(String(100))
    fecha_registro  = Column(DateTime, default=datetime.utcnow)
```

**¿Qué hace `Base = declarative_base()`?**
Crea un registro interno donde SQLAlchemy apunta todas las clases
que hereden de `Base`. Cuando llamas a `Base.metadata.create_all(engine)`,
recorre ese registro y genera el SQL necesario para cada tabla.

**¿Qué hace `Column(...)`?**
Define una columna de la tabla. Los tipos (`Integer`, `String`, `DateTime`)
se traducen automáticamente al tipo equivalente en MariaDB.

---

## `database/connection.py` — Engine y sesión

```python
engine = create_engine("mysql+pymysql://user:pass@host:port/db")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

**¿Qué es el `engine`?**
Es el objeto que representa la conexión a MariaDB. No abre una conexión
inmediatamente — la abre cuando realmente se necesita (lazy).

**¿Qué es `SessionLocal`?**
Es una fábrica de sesiones. Cada vez que llamas a `SessionLocal()`
obtienes una sesión nueva (equivale a una transacción en SQL).
Debes cerrarla con `session.close()` cuando termines.

**¿Por qué `autocommit=False`?**
Para controlar tú manualmente cuándo se confirman los cambios
con `session.commit()`. Si algo falla, puedes hacer `session.rollback()`.

---

## `database/setup_db.py` — Inicialización

Este script se ejecuta **una sola vez** para preparar el entorno:

1. Se conecta a MariaDB **sin especificar base de datos** (con pymysql puro)
2. Crea la base de datos si no existe (`CREATE DATABASE IF NOT EXISTS`)
3. Importa `Base` desde `models/usuario.py`
4. Llama a `Base.metadata.create_all(engine)` → crea todas las tablas

```bash
# Ejecutar desde la raíz del proyecto
python database/setup_db.py
```

**¿Por qué no puede hacer el ORM el paso 1?**
SQLAlchemy necesita conectarse a una base de datos para operar, pero esa
base de datos aún no existe. Por eso el primer paso se hace con pymysql
directamente contra el servidor, sin especificar BD.

---

## Errores frecuentes

| Error | Causa | Solución |
|-------|-------|----------|
| `Access denied for user` | Usuario/contraseña incorrectos en `.env` | Revisar `.env` |
| `Can't connect to MySQL server` | MariaDB no está corriendo | `sudo systemctl start mariadb` |
| `int() argument must be a string... not 'NoneType'` | `MARIADB_PORT` no está en el `.env` | Añadir `MARIADB_PORT=3306` al `.env` |
| `ModuleNotFoundError: pymysql` | PyMySQL no instalado | `pip install pymysql` |
| `No module named 'models'` | Script ejecutado desde directorio incorrecto | Ejecutar desde la raíz del proyecto |

---

## Flujo completo resumido

```
.env
 │
 ▼
connection.py  →  lee credenciales → crea engine + SessionLocal
 │
 ▼
setup_db.py    →  importa Base (desde models/) → create_all(engine) → tabla creada en MariaDB
 │
 ▼
user_service.py → usa SessionLocal para guardar/buscar usuarios
 │
 ▼
actions.py     → importa user_service → llama guardar/buscar desde las acciones de Rasa
```
