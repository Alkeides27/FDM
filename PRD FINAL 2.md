# PRD — Integración DolarAPI para tasa BCV automática (v1.3)

**Proyecto:** IngeniumCode-FDM
**Rama:** `Módulo-de-Pagos`
**Versión:** 1.3 (mejora de UX)
**Fecha:** 2026-04-29
**Plazo estimado:** 1.5 - 2 horas

---

## 0. Instrucciones para la IA ejecutora

Esta mejora elimina la fricción de que el admin tenga que copiar la tasa BCV manualmente desde bcv.org.ve cada vez que aprueba un pago. La integración con **DolarAPI** (API pública gratuita) trae la tasa oficial automáticamente, con cache local para evitar llamadas redundantes y tolerancia a fallos para no romper el flujo si la API está caída.

NO toca lógica de cobertura ni redondeo (eso ya está cubierto en v1.2). Solo agrega automatización de la tasa.

Trabaja sobre la rama `Módulo-de-Pagos`. Ejecuta las fases en orden. Commit después de cada fase.

---

## 1. Contexto

### 1.1 Estado actual

En la versión 1.2, cuando el admin aprueba un pago, debe:

1. Abrir bcv.org.ve en otra pestaña.
2. Copiar la tasa del día.
3. Pegarla en el form de aprobación.
4. Aprobar.

Esto es fricción innecesaria, propenso a errores de transcripción, y desactualizado si el admin no actualiza la tasa cada día.

### 1.2 Solución

Integrar con **DolarAPI** (https://ve.dolarapi.com/v1/dolares/oficial), una API pública gratuita de código abierto que expone la tasa oficial venezolana actualizada diariamente. La tasa se trae automáticamente al abrir el formulario de aprobación, con un **fallback manual** si la API está caída.

### 1.3 ¿Por qué esta API y no scrapear bcv.org.ve?

| Criterio | DolarAPI | Scrape BCV |
|---|---|---|
| Estabilidad | API pública con SLA implícito | Frágil, rompe si BCV cambia HTML |
| Mantenimiento | Cero, ellos lo mantienen | Reescribir cada vez que cambia el sitio |
| Velocidad | < 200ms | ~2s + parsing |
| Costo | Gratis (open source, MIT) | Gratis pero alto costo de mantenimiento |
| Tasa correcta | Sí, fuente oficial | Sí |
| Histórico | Sí, endpoint dedicado | No, scrape diario manual |

**Decisión:** DolarAPI gana en todos los ejes. Scrape de BCV queda descartado.

---

## 2. Endpoints de DolarAPI a usar

### 2.1 Tasa oficial actual

```
GET https://ve.dolarapi.com/v1/dolares/oficial
```

**Respuesta real verificada (2026-04-29):**

```json
{
  "moneda": "USD",
  "fuente": "oficial",
  "nombre": "Dólar",
  "compra": null,
  "venta": null,
  "promedio": 486.1955,
  "fechaActualizacion": "2026-04-29T00:00:00-04:00"
}
```

**Campos relevantes:**
- `promedio`: la tasa del día (Bs por USD). Este es el valor a usar.
- `fechaActualizacion`: ISO 8601 con timezone Caracas (`-04:00`).

### 2.2 Histórico (para pagos con fecha pasada)

```
GET https://ve.dolarapi.com/v1/historicos/dolares/oficial
```

**Respuesta:** array con la tasa de cada día, ordenada cronológicamente. Útil cuando el representante reporta un pago de hace varios días — debemos usar la tasa del día del pago, no la de hoy.

```json
[
  {
    "fuente": "oficial",
    "compra": 0,
    "venta": 0,
    "promedio": 480.5,
    "fecha": "2026-04-25T00:00:00-04:00"
  },
  ...
]
```

### 2.3 Sin autenticación, sin API key

La API es pública. No requiere token, header especial ni rate limiting estricto documentado. Cortesía profesional: no llamar más de necesario.

---

## 3. Decisiones de diseño

### 3.1 Cache local en BD

**Problema:** si el admin aprueba 10 pagos seguidos del mismo día, no tiene sentido llamar la API 10 veces.

**Solución:** modelo `TasaBCV` que cachea la tasa por fecha. Antes de llamar la API, se consulta el cache. Si existe la tasa para esa fecha, se usa. Si no, se llama la API y se guarda.

### 3.2 Cuándo se trae la tasa

**Opción A:** al abrir el detalle del pago (admin) → se carga la tasa del día del pago automáticamente.
**Opción B:** al hacer click en "Aprobar" → se trae en ese momento.
**Opción C:** ambas — se carga al detalle y también se refresca al aprobar.

**Decisión: Opción A.** El admin ve la tasa precargada en el campo desde que abre el pago. Si la API estaba caída, el campo queda vacío y el admin la ingresa manualmente. Simplest path.

### 3.3 Tolerancia a fallos

Si DolarAPI está caída, lenta, o devuelve un formato inesperado, **NUNCA romper el flujo de aprobación**. El admin debe poder seguir aprobando pagos manualmente como hasta ahora. Se loggea el error pero no se propaga.

### 3.4 Tasa por fecha del pago, no del día actual

**Caso real:** representante reporta hoy (29 abril) un pago que hizo el 25 de abril. La tasa correcta es la del 25, no la del 29.

**Solución:** al aprobar, se intenta traer la tasa de `fecha_pago` desde el endpoint histórico. Si está disponible, se usa. Si no (o si `fecha_pago == hoy`), se usa la tasa actual.

### 3.5 Override manual

El admin siempre puede sobreescribir la tasa precargada. El campo del form sigue siendo editable. Esto cubre casos especiales (negociaciones, paralelo, errores de la API).

---

## 4. FASE 1 — Modelo de cache

**Archivo:** `finanzas/models.py`
**Tiempo:** 15 min.

### 4.1 Agregar el modelo `TasaBCV`

Justo antes del modelo `Mensualidad`, agregar:

```python
class TasaBCV(models.Model):
    """Cache local de la tasa BCV. Una fila por fecha."""
    fecha = models.DateField(unique=True, db_index=True)
    tasa = models.DecimalField(
        max_digits=12, decimal_places=4,
        help_text="Bolívares por USD"
    )
    fuente = models.CharField(
        max_length=20, default='dolarapi',
        help_text="Origen: dolarapi, manual, etc."
    )
    capturada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Tasa BCV'
        verbose_name_plural = 'Tasas BCV'

    def __str__(self):
        return f"{self.fecha}: {self.tasa} Bs/USD ({self.fuente})"
```

### 4.2 Migración

```bash
python manage.py makemigrations finanzas
python manage.py migrate
```

### 4.3 Registrar en admin

En `finanzas/admin.py`, agregar:

```python
from .models import TasaBCV

@admin.register(TasaBCV)
class TasaBCVAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tasa', 'fuente', 'capturada_en')
    list_filter = ('fuente',)
    date_hierarchy = 'fecha'
    ordering = ('-fecha',)
```

### 4.4 Commit

```bash
git add finanzas/models.py finanzas/admin.py finanzas/migrations/
git commit -m "feat(finanzas): modelo TasaBCV para cache de tasas"
```

---

## 5. FASE 2 — Servicio de integración con DolarAPI

**Archivo nuevo:** `finanzas/services/__init__.py` y `finanzas/services/tasa_bcv.py`
**Tiempo:** 30 min.

### 5.1 Crear estructura

```bash
mkdir -p finanzas/services
touch finanzas/services/__init__.py
```

### 5.2 Crear `finanzas/services/tasa_bcv.py`

```python
# finanzas/services/tasa_bcv.py
"""
Servicio de integración con DolarAPI (https://ve.dolarapi.com).
Provee la tasa oficial BCV con cache local y tolerancia a fallos.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
import requests
from django.utils import timezone
from finanzas.models import TasaBCV

logger = logging.getLogger(__name__)

API_BASE = 'https://ve.dolarapi.com/v1'
ENDPOINT_ACTUAL = f'{API_BASE}/dolares/oficial'
ENDPOINT_HISTORICO = f'{API_BASE}/historicos/dolares/oficial'
TIMEOUT_SEGUNDOS = 5


def obtener_tasa(fecha_objetivo=None):
    """
    Devuelve la tasa BCV para una fecha. Si no se especifica, hoy.

    Flujo:
    1. Buscar en cache local (TasaBCV).
    2. Si no existe, llamar DolarAPI.
    3. Guardar en cache.
    4. Devolver Decimal o None si falla todo.

    Args:
        fecha_objetivo: date. Si None, usa hoy en zona Caracas.

    Returns:
        Decimal con la tasa, o None si no se pudo obtener.
    """
    if fecha_objetivo is None:
        fecha_objetivo = timezone.localdate()

    # 1. Cache hit
    cache = TasaBCV.objects.filter(fecha=fecha_objetivo).first()
    if cache:
        logger.debug(f'TasaBCV cache HIT para {fecha_objetivo}: {cache.tasa}')
        return cache.tasa

    # 2. Cache miss → API
    es_hoy = fecha_objetivo == timezone.localdate()

    try:
        if es_hoy:
            tasa = _fetch_actual()
        else:
            tasa = _fetch_historico(fecha_objetivo)
    except Exception as e:
        logger.warning(f'DolarAPI falló para {fecha_objetivo}: {e}')
        return None

    if tasa is None:
        return None

    # 3. Guardar en cache (idempotente)
    TasaBCV.objects.update_or_create(
        fecha=fecha_objetivo,
        defaults={'tasa': tasa, 'fuente': 'dolarapi'}
    )
    logger.info(f'TasaBCV API HIT para {fecha_objetivo}: {tasa}')
    return tasa


def _fetch_actual():
    """Trae la tasa del día desde DolarAPI."""
    r = requests.get(ENDPOINT_ACTUAL, timeout=TIMEOUT_SEGUNDOS)
    r.raise_for_status()
    data = r.json()
    promedio = data.get('promedio')
    if promedio is None or promedio == 0:
        logger.warning(f'DolarAPI devolvió promedio inválido: {data}')
        return None
    return Decimal(str(promedio))


def _fetch_historico(fecha_objetivo):
    """
    Trae el histórico completo y busca la tasa del día solicitado.
    Si no hay tasa exacta para esa fecha, usa la del día anterior más cercano.
    """
    r = requests.get(ENDPOINT_HISTORICO, timeout=TIMEOUT_SEGUNDOS)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        return None

    # Filtrar entradas con fecha <= fecha_objetivo, ordenar descendente, tomar primera
    candidatas = []
    for entry in data:
        try:
            fecha_str = entry.get('fecha', '')
            fecha_entry = datetime.fromisoformat(fecha_str).date()
            promedio = entry.get('promedio')
            if promedio and fecha_entry <= fecha_objetivo:
                candidatas.append((fecha_entry, Decimal(str(promedio))))
        except (ValueError, TypeError):
            continue

    if not candidatas:
        return None

    # La más cercana hacia atrás
    candidatas.sort(key=lambda x: x[0], reverse=True)
    return candidatas[0][1]


def refrescar_tasa_actual():
    """
    Fuerza la actualización de la tasa de hoy ignorando cache.
    Útil para un management command diario o botón de admin.
    """
    fecha_hoy = timezone.localdate()
    try:
        tasa = _fetch_actual()
    except Exception as e:
        logger.error(f'No se pudo refrescar tasa: {e}')
        return None

    if tasa is None:
        return None

    TasaBCV.objects.update_or_create(
        fecha=fecha_hoy,
        defaults={'tasa': tasa, 'fuente': 'dolarapi'}
    )
    return tasa
```

### 5.3 Probar manualmente

```bash
python manage.py shell
```

```python
from finanzas.services.tasa_bcv import obtener_tasa, refrescar_tasa_actual
from datetime import date

# Tasa de hoy
print(obtener_tasa())   # Decimal('486.1955') o similar

# Tasa de fecha pasada
print(obtener_tasa(date(2026, 4, 25)))

# Forzar refresh
print(refrescar_tasa_actual())
```

### 5.4 Commit

```bash
git add finanzas/services/
git commit -m "feat(finanzas): servicio de integración con DolarAPI + cache local"
```

---

## 6. FASE 3 — Pre-cargar tasa en form de aprobación

**Archivos:** `finanzas/views.py`, `templates/finanzas/detalle.html`
**Tiempo:** 20 min.

### 6.1 Modificar `detalle_admin` en `finanzas/views.py`

Buscar la función actual:

```python
@user_passes_test(es_admin)
def detalle_admin(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    audit = pago.audit_log.all()[:20]
    mensualidades = pago.mensualidades_cubiertas.all()
    total_esperado_usd = sum(
        (m.monto_usd for m in mensualidades),
        Decimal('0.00')
    )
    return render(request, 'finanzas/detalle.html', {
        'pago': pago,
        'audit_log': audit,
        'aprobar_form': AprobarPagoForm(),
        'rechazar_form': RechazarPagoForm(),
        'total_esperado_usd': total_esperado_usd,
    })
```

Reemplazar por:

```python
@user_passes_test(es_admin)
def detalle_admin(request, pk):
    pago = get_object_or_404(Pago, pk=pk)
    audit = pago.audit_log.all()[:20]
    mensualidades = pago.mensualidades_cubiertas.all()
    total_esperado_usd = sum(
        (m.monto_usd for m in mensualidades),
        Decimal('0.00')
    )

    # Pre-cargar tasa BCV de la fecha del pago (no rompe si falla)
    tasa_sugerida = None
    fuente_tasa = None
    if pago.estado == 'PENDIENTE':
        from finanzas.services.tasa_bcv import obtener_tasa
        tasa_sugerida = obtener_tasa(pago.fecha_pago)
        if tasa_sugerida is not None:
            from .models import TasaBCV
            cache_obj = TasaBCV.objects.filter(fecha=pago.fecha_pago).first()
            fuente_tasa = cache_obj.fuente if cache_obj else 'dolarapi'

    aprobar_form = AprobarPagoForm(
        initial={'tasa_bcv': tasa_sugerida} if tasa_sugerida else None
    )

    return render(request, 'finanzas/detalle.html', {
        'pago': pago,
        'audit_log': audit,
        'aprobar_form': aprobar_form,
        'rechazar_form': RechazarPagoForm(),
        'total_esperado_usd': total_esperado_usd,
        'tasa_sugerida': tasa_sugerida,
        'fuente_tasa': fuente_tasa,
    })
```

### 6.2 Modificar `templates/finanzas/detalle.html`

Buscar el bloque de aprobación:

```html
{% if pago.estado == 'PENDIENTE' %}
  <div class="border rounded p-4 bg-green-50">
    <h3 class="font-bold mb-2">Aprobar</h3>
    <form method="post" action="{% url 'finanzas:aprobar' pago.id %}" class="space-y-2">
      {% csrf_token %}
      <label class="block text-sm">Tasa BCV (Bs por USD)</label>
      {{ aprobar_form.tasa_bcv }}
      <button class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">Aprobar pago</button>
    </form>
  </div>
```

Reemplazar por:

```html
{% if pago.estado == 'PENDIENTE' %}
  <div class="border rounded p-4 bg-green-50">
    <h3 class="font-bold mb-2">Aprobar</h3>
    <form method="post" action="{% url 'finanzas:aprobar' pago.id %}" class="space-y-2">
      {% csrf_token %}
      <label class="block text-sm">Tasa BCV (Bs por USD)</label>
      {{ aprobar_form.tasa_bcv }}

      {% if tasa_sugerida %}
        <p class="text-xs text-gray-600">
          ✓ Tasa pre-cargada desde
          <strong>{{ fuente_tasa|default:"DolarAPI" }}</strong>
          para la fecha {{ pago.fecha_pago }}.
          Puedes editarla si es necesario.
        </p>
      {% else %}
        <p class="text-xs text-amber-700">
          ⚠️ No se pudo obtener la tasa automáticamente. Cópiala desde
          <a href="https://www.bcv.org.ve" target="_blank" class="underline">bcv.org.ve</a>.
        </p>
      {% endif %}

      <button class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">Aprobar pago</button>
    </form>
  </div>
```

### 6.3 Commit

```bash
git add finanzas/views.py templates/finanzas/detalle.html
git commit -m "feat(finanzas): pre-cargar tasa BCV automáticamente al revisar pago"
```

---

## 7. FASE 4 — Management command para refrescar tasa

**Archivo nuevo:** `finanzas/management/commands/refrescar_tasa_bcv.py`
**Tiempo:** 10 min.

### 7.1 Crear el comando

Asumiendo que ya existe la estructura `finanzas/management/commands/` (de la Fase 4 del PRD anterior):

```python
# finanzas/management/commands/refrescar_tasa_bcv.py
from django.core.management.base import BaseCommand
from finanzas.services.tasa_bcv import refrescar_tasa_actual


class Command(BaseCommand):
    help = 'Refresca la tasa BCV del día desde DolarAPI.'

    def handle(self, *args, **opts):
        tasa = refrescar_tasa_actual()
        if tasa is None:
            self.stdout.write(self.style.ERROR(
                'No se pudo obtener la tasa. Verifica conectividad con DolarAPI.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Tasa BCV de hoy actualizada: {tasa} Bs/USD'
            ))
```

### 7.2 Probar

```bash
python manage.py refrescar_tasa_bcv
```

**Resultado esperado:**
```
Tasa BCV de hoy actualizada: 486.1955 Bs/USD
```

### 7.3 Documentar uso recurrente

Agregar al `README.md`, sección de comandos:

```markdown
- `python manage.py refrescar_tasa_bcv` — actualiza la tasa BCV del día desde DolarAPI.
  Recomendado correrlo a primera hora del día vía cron/scheduled task.
  En producción ejemplo cron: `0 9 * * * python manage.py refrescar_tasa_bcv`
```

### 7.4 Commit

```bash
git add finanzas/management/commands/refrescar_tasa_bcv.py README.md
git commit -m "feat(finanzas): management command refrescar_tasa_bcv"
```

---

## 8. FASE 5 — Mostrar tasa actual al representante (opcional pero útil)

**Archivo:** `templates/finanzas/reportar.html`
**Tiempo:** 10 min.

Esto le da contexto al representante mientras llena el form: ve cuántos bolívares debe pagar para cubrir su mensualidad de USD.

### 8.1 Modificar `reportar_pago` en `views.py`

Buscar:

```python
else:
    form = ReportarPagoForm(representante=rep)

return render(request, 'finanzas/reportar.html', {'form': form})
```

Reemplazar por:

```python
else:
    form = ReportarPagoForm(representante=rep)

# Tasa de hoy para mostrar referencia (no rompe si falla)
from finanzas.services.tasa_bcv import obtener_tasa
tasa_hoy = obtener_tasa()

return render(request, 'finanzas/reportar.html', {
    'form': form,
    'tasa_hoy': tasa_hoy,
})
```

### 8.2 Modificar `templates/finanzas/reportar.html`

Justo después de `<h1>Reportar pago</h1>`, agregar:

```html
{% if tasa_hoy %}
  <div class="p-2 mb-4 bg-blue-50 text-blue-900 rounded text-sm">
    📊 Tasa BCV de hoy: <strong>{{ tasa_hoy }} Bs/USD</strong>
    <span class="text-xs text-blue-700">(referencia automática desde DolarAPI)</span>
  </div>
{% endif %}
```

### 8.3 Commit

```bash
git add finanzas/views.py templates/finanzas/reportar.html
git commit -m "feat(finanzas): mostrar tasa BCV de referencia al representante"
```

---

## 9. FASE 6 — QA

**Tiempo:** 20 min.

### 9.1 Tests manuales

**Test de tasa actual:**

- [ ] Como representante, ir a `/finanzas/reportar/`.
- [ ] Verificar banner azul con tasa BCV de hoy.
- [ ] Reportar un pago con `fecha_pago` = hoy.
- [ ] Como admin, abrir el detalle del pago.
- [ ] Verificar que el campo "Tasa BCV" aparece pre-llenado con un valor cercano a 486.
- [ ] Verificar el texto "✓ Tasa pre-cargada desde DolarAPI para la fecha [hoy]".
- [ ] Aprobar sin modificar la tasa.
- [ ] Verificar que el pago se aprueba correctamente.

**Test de fecha pasada:**

- [ ] Como representante, reportar pago con `fecha_pago` de hace 5 días.
- [ ] Como admin, abrir el detalle.
- [ ] Verificar que la tasa pre-cargada corresponde a esa fecha histórica (puede ser distinta a la de hoy).
- [ ] Verificar el texto "para la fecha [esa fecha pasada]".

**Test de cache:**

- [ ] Aprobar 3 pagos seguidos del mismo día.
- [ ] Ir a Django admin → Finanzas → Tasas BCV.
- [ ] Verificar que solo hay UNA fila por fecha (no se duplica).
- [ ] Cambiar la red (apagar wifi por 1 minuto).
- [ ] Abrir otro pago del mismo día → debe seguir mostrando la tasa cacheada.

**Test de fallo de API:**

- [ ] Desconectar internet.
- [ ] Reportar un pago con fecha de hoy.
- [ ] Borrar manualmente desde Django admin la entrada de TasaBCV de hoy.
- [ ] Como admin, abrir el detalle del pago.
- [ ] Verificar que aparece "⚠️ No se pudo obtener la tasa automáticamente" con link a bcv.org.ve.
- [ ] Ingresar tasa manual y aprobar.
- [ ] Verificar que el pago se aprueba.

**Test del management command:**

- [ ] Ejecutar `python manage.py refrescar_tasa_bcv`.
- [ ] Verificar mensaje de éxito.
- [ ] Ejecutarlo dos veces seguidas → debe funcionar idempotentemente.

**Test de override manual:**

- [ ] Abrir un pago pendiente, ver la tasa pre-cargada (ej: 486).
- [ ] Cambiarla a 480 manualmente.
- [ ] Aprobar.
- [ ] Verificar que el pago quedó con tasa 480, no 486.

### 9.2 Commit final

```bash
git add -A
git commit -m "chore(finanzas): QA de integración DolarAPI v1.3"
```

---

## 10. Trampas conocidas

1. **DolarAPI puede tardar.** El timeout está en 5s. Si la red del servidor es lenta, considerar bajarlo a 3s o subirlo si la API es estable. Nunca subir más de 10s o bloquea la UI.

2. **`requests` ya está instalado** desde la integración de Telegram (v1.1). No requiere instalación adicional.

3. **El campo `compra` y `venta` pueden venir `null`** en la respuesta de DolarAPI — solo `promedio` es confiable. El servicio ya maneja esto.

4. **Timezone Caracas (`America/Caracas`, UTC-4)** ya está configurado en `settings.py`. `timezone.localdate()` devuelve la fecha correcta. NO usar `date.today()` directo (puede dar el día anterior si el servidor está en UTC).

5. **El histórico de DolarAPI puede no tener fechas muy antiguas.** Si un representante reporta un pago de hace 6+ meses (caso raro), la API puede no devolver datos. El servicio devuelve `None` y el admin ingresa manualmente.

6. **NO llamar a DolarAPI desde el form del representante en cada keystroke.** La llamada está solo al cargar la vista (en `reportar_pago` GET y `detalle_admin` GET). No hay AJAX en este parche.

7. **La tasa cacheada NO se actualiza sola si DolarAPI corrige un valor.** Si DolarAPI publica 486 y luego corrige a 487, el cache local sigue en 486. Para forzar refresh: `python manage.py refrescar_tasa_bcv` o borrar la fila del admin.

8. **El campo `tasa_sugerida` en el contexto del template puede ser `None`.** El template ya maneja ese caso con un `{% if %}`.

9. **No exponer DolarAPI directamente al frontend del representante** vía AJAX. Toda llamada pasa por el servidor — esto evita CORS, mantiene el cache compartido, y deja un único punto de mantenimiento.

---

## 11. Resumen del plan

| Fase | Tarea | Tiempo | Commit |
|---|---|---|---|
| **1** | Modelo TasaBCV + admin | 15 min | `feat(finanzas): modelo TasaBCV para cache de tasas` |
| **2** | Servicio integración DolarAPI | 30 min | `feat(finanzas): servicio de integración con DolarAPI + cache local` |
| **3** | Pre-cargar tasa en detalle admin | 20 min | `feat(finanzas): pre-cargar tasa BCV automáticamente al revisar pago` |
| **4** | Management command | 10 min | `feat(finanzas): management command refrescar_tasa_bcv` |
| **5** | Tasa de referencia para representante | 10 min | `feat(finanzas): mostrar tasa BCV de referencia al representante` |
| **6** | QA | 20 min | `chore(finanzas): QA de integración DolarAPI v1.3` |
| **TOTAL** | | **~1h 45min** | |

---

## 12. Mensaje de PR sugerido

```
feat: integración con DolarAPI para tasa BCV automática

## Cambios
- Modelo TasaBCV para cache local de tasas por fecha
- Servicio de integración con DolarAPI (https://ve.dolarapi.com)
  - Endpoint actual: /v1/dolares/oficial
  - Endpoint histórico: /v1/historicos/dolares/oficial
- Pre-carga automática de tasa al abrir detalle de pago
  - Usa fecha_pago para traer tasa histórica si no es hoy
  - Tolerancia a fallos: si la API cae, admin ingresa manual
- Tasa de referencia visible para representante en el form
- Management command `refrescar_tasa_bcv` para actualización diaria

## Beneficios
- Admin ya no copia/pega tasa desde bcv.org.ve
- Tasa correcta automática para pagos de fechas pasadas
- Cache local elimina llamadas redundantes
- Override manual sigue disponible para casos especiales
```

---

**Fin del PRD.**

---

