import os
import sys
import platform
import subprocess


def start_celery():
    """Inicia Celery con la configuración correcta según el sistema"""

    system = platform.system()

    if system == "Windows":
        print("🚀 Iniciando Celery en Windows...")
        cmd = [
            "celery", "-A", "inova", "worker",
            "-l", "INFO",
            "--pool=solo",
            "--without-gossip",
            "--without-mingle"
        ]
    else:
        print("🚀 Iniciando Celery en Linux/Unix...")
        cmd = [
            "celery", "-A", "inova", "worker",
            "-l", "INFO",
            "--pool=prefork",
            "--concurrency=4",
            "--without-gossip",
            "--without-mingle"
        ]

    print(f"📍 Comando: {' '.join(cmd)}")

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n⏹️ Celery detenido")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    start_celery()