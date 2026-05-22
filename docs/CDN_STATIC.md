# CDN para estáticos del portal (roadmap #25)

Sirve CSS/JS del portal desde un CDN en lugar del proceso Gunicorn.

## Ya implementado

En `settings.py`:

```python
STATIC_URL = CDN_STATIC_URL + '/'  # si está definido
```

## Configuración

1. Ejecutar en el servidor:

```bash
python manage.py collectstatic --noinput
```

2. Subir contenido de `staticfiles/` al bucket/CDN (S3, CloudFront, etc.).

3. En `.env`:

```env
CDN_STATIC_URL=https://cdn.tudominio.com/static
```

4. Reiniciar Gunicorn.

Las plantillas usan `{% static %}` y tomarán la URL del CDN.

## nginx

Sigue sirviendo `/static/` como fallback si no usas CDN, o elimina el `location /static/` si todo va al CDN.

## Desarrollo local

No definir `CDN_STATIC_URL`; se usa `/static/` con WhiteNoise/finders.

## Referencias

- [DESPLIEGUE.md](./DESPLIEGUE.md)
