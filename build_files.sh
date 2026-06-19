#!/bin/bash

# Detener ejecución si ocurre algún error
set -e

echo "=== INICIANDO PROCESO DE CONSTRUCCIÓN EN VERCEL ==="

# 1. Instalar dependencias de Python
echo "Instalando dependencias de Python..."
python3 -m pip install -r requirements.txt

# 2. Instalar dependencias de Node.js (esbuild, tailwindcss, etc.)
echo "Instalando dependencias de Node.js..."
npm install

# 3. Compilar Tailwind CSS
echo "Compilando Tailwind CSS..."
npx tailwindcss -i ./core/static/css/input.css -o ./core/static/css/output.css --minify

# 4. Compilar JavaScript bundle
echo "Compilando archivos JavaScript con esbuild..."
npm run build:js

# 5. Recopilar archivos estáticos de Django en el STATIC_ROOT (staticfiles)
echo "Ejecutando collectstatic..."
python3 manage.py collectstatic --noinput --clear

echo "=== PROCESO DE CONSTRUCCIÓN COMPLETADO CON ÉXITO ==="
