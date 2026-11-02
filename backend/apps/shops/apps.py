import os
import sys
from django.apps import AppConfig

_migrated = False

class ShopsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shops'
    verbose_name = 'Shops & Products'

    def ready(self):
        global _migrated
        if _migrated:
            return
        _migrated = True

        # Auto-apply migrations only when running dev server (runserver reloader child)
        is_runserver = any('runserver' in arg for arg in sys.argv)
        is_reloader_child = os.environ.get('RUN_MAIN') == 'true'
        if is_runserver and is_reloader_child:
            try:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
            except Exception as e:
                print(f"[Auto-Migrate Notice]: {e}")

