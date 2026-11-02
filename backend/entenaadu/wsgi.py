"""
WSGI config for entenaadu project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'entenaadu.settings')
application = get_wsgi_application()
