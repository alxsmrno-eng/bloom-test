# Kay Listener

Kay Listener es una aplicación de escritorio para Windows 11 escrita en Python 3.11. Escucha el micrófono en segundo plano, activa la grabación al oír la frase de activación "Oye Kay" y envía el audio resultante a un webhook configurable. Todo el procesamiento se realiza de forma local usando el motor de reconocimiento de voz offline de Vosk.

## Flujo general

```
+-------------+      +------------------+      +----------------+      +----------------------+      +----------------+
| AudioStream | ---> | WakeDetector     | ---> | Recorder       | ---> | Uploader / Spooler  | ---> | Webhook / Cola |
+-------------+      +------------------+      +----------------+      +----------------------+      +----------------+
        ^                      |                       |                            |                        |
        |                      +------- notificaciones y logs ---------------------+                        |
        +-------------------- Bandeja del sistema ---------------------------------+------------------------+
```

## Requisitos

- Windows 11
- Python 3.11
- Micrófono funcional con permisos otorgados

## Instalación

```powershell
# Clonar e instalar
git clone <REPO_URL> kay-listener
cd kay-listener
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt

# Variables de entorno
copy .env.example .env
notepad .env   # pega tu WEBHOOK_URL

# Descargar modelo Vosk (o se hace en el primer arranque)
python scripts/download_vosk_model.py

# Ejecutar
python -m app.app
```

## Uso

1. Al iniciar, la aplicación cargará el modelo de wake word y comenzará a escuchar el micrófono.
2. Al detectar la frase "Oye Kay" (insensible a mayúsculas y pequeñas variaciones), comienza la grabación.
3. Cuando haya 5 segundos (configurable) de silencio continuo la grabación finaliza y se envía al webhook configurado.
4. Se muestran notificaciones del sistema y se registran los eventos en `logs/app.log`.

## Menú de bandeja

- **Iniciar/Pausar escucha**: Activa o desactiva la escucha continua.
- **Probar micrófono**: Realiza una grabación corta de prueba.
- **Abrir carpeta logs**: Abre el directorio de logs en el explorador.
- **Salir**: Cierra la aplicación por completo.

## Construir ejecutable (.exe)

```powershell
.\.venv\Scripts\activate
.\build.bat
# genera .\dist\KayListener\KayListener.exe
```

## Ejecutar al iniciar Windows

1. Abrir **Task Scheduler** (Programador de tareas).
2. Crear tarea básica: Nombre "Kay Listener".
3. Disparador: "Al iniciar sesión".
4. Acción: "Iniciar un programa" → seleccionar `KayListener.exe` generado.
5. Marcar "Iniciar minimizado" en propiedades adicionales.
6. Guardar la tarea.

## Verificación

- Al ejecutar, debe aparecer un icono en la bandeja del sistema (si PyStray/Pillow están disponibles) y el log `logs/app.log` mostrará "Escuchando...".
- Decir "Oye Kay" → ver notificación "Grabando...".
- Tras guardar, se envía el WAV y aparece notificación con el resultado (`200 OK` o "Encolado").

## Solución de problemas

- **Micrófono no detectado**: Ejecuta `python -m app.app --list-devices` para ver los índices disponibles y configúralo en `.env` (INPUT_DEVICE_INDEX).
- **Sin permisos**: Asegúrate de permitir acceso al micrófono para Python en la configuración de privacidad de Windows.
- **Latencia o cortes**: Ajusta `SILENCE_SECONDS` y `VAD_AGGRESSIVENESS` en `.env`.
- **Uso de CPU elevado**: Verifica que no haya múltiples instancias ejecutándose.
- **Webhook caído**: Los envíos fallidos se guardan en `outbox/` y se reintentan automáticamente.

## Seguridad y privacidad

- Todo el procesamiento de voz ocurre en local.
- Solo el archivo WAV final se envía al webhook configurado.
- El contenido del audio no se almacena permanentemente; los archivos en `outbox/` se eliminan tras un envío exitoso.

## Desinstalación

1. Eliminar la tarea programada en Task Scheduler.
2. Borrar `.venv`, `dist/`, `build/`, `models/` y cualquier otro directorio generado.
3. Eliminar la carpeta `kay-listener`.

## Desarrollo

- Ejecuta `ruff` y `black` para lint/format.
- `pytest` corre los tests unitarios.
- `mypy` valida tipos (modo suave).

## Licencia

MIT. Consulta `LICENSE` para más detalles.
