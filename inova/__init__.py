# inova/__init__.py
from __future__ import absolute_import, unicode_literals

# Esto asegura que la app de Celery sea cargada cuando Django inicie
from .celery import app as celery_app

__all__ = ('celery_app',)