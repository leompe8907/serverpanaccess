# CI/CD — GitHub Actions (roadmap #28)

Pipeline en `.github/workflows/ci.yml` que corre en cada **push** y **pull request** a `main`, `master` o `develop`.

## Jobs

| Job | Qué hace |
|-----|----------|
| **django-check** | `manage.py check` + `check_deploy` |
| **test** | `migrate` + `manage.py test wind.tests` (SQLite) |
| **redis-check** | Servicio Redis en el runner + `check_redis` |

## Variables en CI

Valores ficticios para PanAccess (no llaman a la API real). `SOCIAL_LOGIN_PROVIDERS` vacío para no exigir Google/Facebook en CI.

`CELERY_TASK_ALWAYS_EAGER=true` — las tareas corren en proceso sin worker.

## Ejecutar tests en local

```bash
python manage.py test wind.tests -v 2
```

## Añadir secretos (staging deploy futuro)

En GitHub → Settings → Secrets, para un workflow de deploy posterior:

- `DEPLOY_HOST`, `SSH_KEY`, etc. (no incluido aún; solo CI de validación)

## Extender el pipeline

1. Job con **PostgreSQL** service (misma imagen que prod).
2. `check_deploy --strict` en rama `main` con secrets de staging.
3. Workflow `workflow_dispatch` para deploy a Ubuntu vía SSH + `systemctl restart`.

## Referencias

- [DEPLOY_UBUNTU_CHECKLIST.md](./DEPLOY_UBUNTU_CHECKLIST.md)
- [ROADMAP_PRODUCCION.md](./ROADMAP_PRODUCCION.md) — ítem #28
