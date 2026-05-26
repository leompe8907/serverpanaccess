# Versiones Python y dependencias

## Versiones objetivo (mayo 2026)

| Componente | Versión |
|------------|---------|
| Python | 3.11+ (3.12 recomendado) |
| Django | **5.2.14** (rama LTS 5.2) |
| DRF | 3.17.x |
| Celery | 5.6.x |

## Archivos de requirements

| Archivo | Uso |
|---------|-----|
| `requirements.txt` | Desarrollo y CI (incluye `psycopg[binary]`) |
| `requirements-dev.txt` | + Locust y herramientas de carga |

## Instalación

```bash
# Desarrollo
python -m venv env
source env/bin/activate   # Linux
# .\env\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt

# Con Locust (staging)
pip install -r requirements-dev.txt

# Producción Ubuntu (psycopg compilado; requiere libpq-dev)
pip install -r requirements.txt
pip install --force-reinstall 'psycopg[c]>=3.2'
```

## Verificación tras instalar

```bash
python -c "import django; print(django.get_version())"
python manage.py check
python manage.py migrate --plan
python manage.py check_deploy --strict   # con .env de staging/prod
```

## Historial

- Antes: `requirements.txt` fijaba `Django==6.0.5` mientras el entorno local usaba 4.2.
- Ahora: **Django 5.2.14** alineado con `settings.py` y validado con `manage.py check`.
