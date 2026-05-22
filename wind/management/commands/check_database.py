"""
Comprueba la conexión a la base de datos configurada en .env (roadmap #1).
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verifica motor de BD, conexión y que no sea SQLite en entornos con DB_ENGINE=postgresql."

    def handle(self, *args, **options):
        settings_dict = connection.settings_dict
        engine = settings_dict.get("ENGINE", "")
        name = settings_dict.get("NAME", "")

        self.stdout.write(f"engine: {engine}")
        self.stdout.write(f"name: {name}")

        if "sqlite" in engine.lower():
            self.stdout.write(
                self.style.WARNING(
                    "Usando SQLite. En Ubuntu prod define DB_ENGINE=django.db.backends.postgresql "
                    "y DB_* en .env (ver docs/POSTGRESQL_UBUNTU.md)."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Motor distinto de SQLite (adecuado para producción)."))

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                row = cursor.fetchone()
            ok = row is not None and row[0] == 1
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"ok: False — {exc}"))
            raise SystemExit(1) from exc

        if ok:
            self.stdout.write(self.style.SUCCESS("ok: True"))
        else:
            self.stdout.write(self.style.ERROR("ok: False"))
            raise SystemExit(1)
