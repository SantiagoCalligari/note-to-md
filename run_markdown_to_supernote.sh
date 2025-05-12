#!/usr/bin/env bash

# Asegúrate de que el script salga si algún comando falla
set -e

# Ruta absoluta a tu directorio de proyecto
PROJECT_DIR="/home/santiago/markdown-to-supernote" # ¡¡¡CAMBIA 'tu_usuario'!!!
SHELL_NIX_FILE="${PROJECT_DIR}/shell.nix"
PYTHON_SCRIPT="${PROJECT_DIR}/main.py"
VENV_ACTIVATOR="${PROJECT_DIR}/.venv/bin/activate"

# Mensaje de inicio para logging
echo "Iniciando la ejecución del script markdown-to-supernote..."
date

# Entrar al entorno de Nix y ejecutar los comandos
# Usamos nix-shell --pure para un entorno más limpio, asegurando que solo lo definido en shell.nix esté presente.
# El comando dentro de --run se ejecuta en un shell bash por defecto.
nix-shell --pure "$SHELL_NIX_FILE" --run "
  echo 'Dentro del entorno nix-shell.'
  echo 'Directorio actual antes de cd:'
  pwd
  cd '$PROJECT_DIR'
  echo 'Directorio actual después de cd:'
  pwd
  echo 'Activando el entorno virtual Python...'
  source '$VENV_ACTIVATOR'
  echo \"Entorno virtual activado: \$VIRTUAL_ENV\"
  echo 'Ejecutando el script de Python...'
  python '$PYTHON_SCRIPT'
  echo 'Script de Python finalizado.'
"

echo "Ejecución de markdown-to-supernote completada."
date

