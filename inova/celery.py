from __future__ import absolute_import, unicode_literals
# ================================
# 8. CONFIGURACIÓN CELERY
# ================================

import os
from celery import Celery

# Establecer el módulo de configuración de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inova.settings')

# Crear instancia de Celery
app = Celery('inova')

# Configurar Celery usando la configuración de Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-descubrir tareas en las apps instaladas
app.autodiscover_tasks()

# Configuración adicional de Celery
app.conf.update(
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutos
    task_soft_time_limit=25 * 60,  # 25 minutos
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
