#!/bin/bash

# Detener ejecución si ocurre algún error
set -e

echo "=== INICIANDO PROCESO DE CONSTRUCCIÓN EN VERCEL ==="

# 1. Crear y activar un entorno virtual temporal para evitar el error de PEP 668 (externally-managed-environment)
echo "Creando entorno virtual temporal..."
python3 -m venv temp_venv
source temp_venv/bin/activate

# 2. Instalar dependencias de Python necesarias para correr collectstatic
echo "Instalando dependencias de Python en el entorno virtual..."
pip install -r requirements.txt

# 3. Instalar dependencias de Node.js (esbuild, tailwindcss, etc.)
echo "Instalando dependencias de Node.js..."
npm install

# 4. Compilar Tailwind CSS
echo "Compilando Tailwind CSS..."
npx tailwindcss -i ./core/static/css/input.css -o ./core/static/css/output.css --minify

# 5. Compilar JavaScript bundle
echo "Compilando archivos JavaScript con esbuild..."
npm run build:js

# 6. Ejecutar migraciones de Django (requiere variables de entorno de la DB)
echo "Ejecutando migraciones de Django..."
python3 manage.py migrate --noinput

# 7. Recopilar archivos estáticos de Django en el STATIC_ROOT (staticfiles)
echo "Ejecutando collectstatic..."
python3 manage.py collectstatic --noinput --clear

# 8. Desactivar y eliminar el entorno virtual temporal para no subirlo a producción
echo "Limpiando entorno virtual temporal..."
deactivate
rm -rf temp_venv

echo "=== PROCESO DE CONSTRUCCIÓN COMPLETADO CON ÉXITO ==="
