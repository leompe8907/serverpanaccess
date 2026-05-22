# PostgreSQL en Ubuntu Server (roadmap #1)

Sin Docker. PostgreSQL instalado en el mismo servidor (o en un host accesible por red privada).

## 1. Instalar PostgreSQL

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

Comprobar:

```bash
sudo systemctl status postgresql
psql --version
```

## 2. Crear usuario y base de datos

Sustituye `TU_PASSWORD_SEGURO` por una contraseña fuerte.

```bash
sudo -u postgres psql <<'EOF'
CREATE USER wind WITH PASSWORD 'TU_PASSWORD_SEGURO';
CREATE DATABASE wind OWNER wind;
GRANT ALL PRIVILEGES ON DATABASE wind TO wind;
\c wind
GRANT ALL ON SCHEMA public TO wind;
EOF
```

Solo conexión local (recomendado si la app está en el mismo servidor):

```bash
# En /etc/postgresql/*/main/pg_hba.conf suele bastar:
# local   all   all   peer
# host    all   all   127.0.0.1/32   scram-sha-256
sudo systemctl reload postgresql
```

## 3. Variables en `.env` del proyecto

En el servidor Ubuntu, en la raíz del proyecto (`win-backend/.env`):

```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=wind
DB_USER=wind
DB_PASSWORD=TU_PASSWORD_SEGURO
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=600
```

**Importante:** usa solo variables `DB_*`. No confundir con `USER` o `HOST` del sistema.

## 4. Migrar esquema Django

Con el venv activado:

```bash
cd /ruta/al/win-backend
source env/bin/activate
pip install -r requirements.txt
python manage.py check_database
python manage.py migrate
```

`check_database` debe imprimir `engine: django.db.backends.postgresql` y `ok: True`.

## 5. Migrar datos desde SQLite (opcional)

Si ya tenías datos en `db.sqlite3` en desarrollo:

```bash
# En la máquina donde está el SQLite (puede ser tu PC):
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.Permission --indent 2 > backup.json

# Copiar backup.json al servidor y, con PostgreSQL ya configurado:
python manage.py migrate
python manage.py loaddata backup.json
```

Revisa que no haya duplicados en tablas con `unique=True` (`code`, `sn`, etc.).

## 6. Pruebas del roadmap #1

| Prueba | Comando / acción | Resultado esperado |
|--------|------------------|-------------------|
| Motor correcto | `python manage.py check_database` | `postgresql`, `ok: True` |
| Esquema | `python manage.py migrate` | Sin errores |
| Escritura | Crear un registro vía admin o API | Persiste tras reiniciar app |
| No SQLite en prod | `ls db.sqlite3` en servidor | No usar este archivo en prod (puede no existir) |

## 7. Copia de seguridad (operación)

```bash
sudo -u postgres pg_dump -Fc wind > wind_$(date +%Y%m%d).dump
```

Restaurar:

```bash
sudo -u postgres pg_restore -d wind -c wind_YYYYMMDD.dump
```

## Solución de problemas

| Error | Causa habitual |
|-------|----------------|
| `password authentication failed` | `DB_PASSWORD` no coincide con `CREATE USER` |
| `connection refused` | PostgreSQL parado o `DB_HOST` incorrecto |
| `permission denied for schema public` | Falta `GRANT` del paso 2 |
| Sigue usando SQLite | Falta `DB_ENGINE=...postgresql` en `.env` del servidor |
