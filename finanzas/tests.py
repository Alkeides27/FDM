# finanzas/tests.py
# Pruebas unitarias — Módulo Finanzas
# PRD v1.0 | IngeniumCode-FDM | 19 de mayo de 2026

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.core.files.uploadedfile import SimpleUploadedFile

from filiacion.models import Representante, Atleta
from administracion.models import Categoria
from finanzas.models import Mensualidad, Pago


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_representante(cedula='V12345678', correo='rep@test.com'):
    """Crea un Representante con datos mínimos válidos."""
    return Representante.objects.create(
        cedula_identidad=cedula,
        nombres='Juan',
        apellidos='Pérez',
        telefono_principal='04141234567',
        direccion_habitacion='Calle de prueba',
        correo_electronico=correo,
    )


def crear_categoria(nombre='Sub-9'):
    """Crea una Categoria con los campos obligatorios reales del modelo.

    Campos confirmados en administracion/models.py:
      - nombre (CharField, max_length=50, unique=True)
      - anio_nacimiento_min (PositiveIntegerField)
      - anio_nacimiento_max (PositiveIntegerField)
      - genero (CharField, choices: MASCULINO, FEMENINO, MIXTO)
    Los demás campos (delegado, coordinador_supervisor, entrenadores_asignados)
    son opcionales (null=True / blank=True / M2M).
    """
    return Categoria.objects.create(
        nombre=nombre,
        anio_nacimiento_min=2017,
        anio_nacimiento_max=2018,
        genero='MASCULINO',
    )


def crear_atleta(representante=None, categoria=None, fecha_nacimiento=None):
    """Crea un Atleta con datos mínimos válidos, construyendo dependencias
    (Representante y Categoria) si no se proporcionan."""
    if representante is None:
        representante = crear_representante()
    if categoria is None:
        categoria = crear_categoria()
    return Atleta.objects.create(
        representante=representante,
        categoria=categoria,
        nombres='Pedro',
        apellidos='Pérez',
        fecha_nacimiento=fecha_nacimiento or date(2017, 3, 15),
        lateralidad='DERECHO',
        posicion='DEL',
    )


def _crear_pago_base(representante, comprobante=None, **overrides):
    """Helper interno para construir un Pago con valores por defecto razonables.
    Acepta overrides para cualquier campo."""
    defaults = {
        'representante': representante,
        'concepto': 'Pago de prueba',
        'metodo': 'PAGO_MOVIL',
        'banco_emisor': '0102',
        'referencia': '',
        'monto_bs': Decimal('100.00'),
        'tasa_bcv': Decimal('50.0000'),
        'fecha_pago': timezone.now().date(),
        'comprobante': comprobante or SimpleUploadedFile(
            'comprobante.pdf', b'contenido_por_defecto',
            content_type='application/pdf',
        ),
        'estado': 'PENDIENTE',
    }
    defaults.update(overrides)
    return Pago.objects.create(**defaults)


# ═══════════════════════════════════════════════════════════════
# FASE 1 — Propiedades calculadas de Mensualidad
# ═══════════════════════════════════════════════════════════════

class Fase1_PropiedadesMensualidadTestCase(TestCase):
    """Valida que las propiedades `etiqueta_periodo` y `vencida`
    retornan exactamente lo esperado, sin dependencias externas."""

    def setUp(self):
        self.atleta = crear_atleta()
        self.hoy = timezone.now().date()

    # --- etiqueta_periodo ---

    def test_etiqueta_periodo_mayo_2026(self):
        """La propiedad etiqueta_periodo debe retornar 'Mayo 2026'
        cuando periodo_mes=5 y periodo_anio=2026."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=5,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        self.assertEqual(m.etiqueta_periodo, 'Mayo 2026')

    def test_etiqueta_periodo_enero_2026(self):
        """La propiedad etiqueta_periodo debe retornar 'Enero 2026'
        para el primer mes del año (periodo_mes=1)."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=1,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        self.assertEqual(m.etiqueta_periodo, 'Enero 2026')

    def test_etiqueta_periodo_diciembre_2026(self):
        """La propiedad etiqueta_periodo debe retornar 'Diciembre 2026'
        para el último mes del año (periodo_mes=12)."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=12,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        self.assertEqual(m.etiqueta_periodo, 'Diciembre 2026')

    # --- vencida ---

    def test_vencida_false_cuando_fecha_futura(self):
        """La propiedad vencida debe ser False cuando la fecha de
        vencimiento es futura y la mensualidad no está pagada."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=6,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=5),
            pagada=False,
        )
        self.assertFalse(m.vencida)

    def test_vencida_true_cuando_fecha_pasada_y_no_pagada(self):
        """La propiedad vencida debe ser True cuando la fecha de
        vencimiento ya pasó y la mensualidad NO está pagada."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=7,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy - timedelta(days=5),
            pagada=False,
        )
        self.assertTrue(m.vencida)

    def test_vencida_false_cuando_pagada_aunque_fecha_pasada(self):
        """La propiedad vencida debe ser False cuando la mensualidad ya
        fue pagada, incluso si la fecha de vencimiento ya pasó."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=8,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy - timedelta(days=30),
            pagada=True,
        )
        self.assertFalse(m.vencida)

    def test_vencida_false_cuando_fecha_es_hoy(self):
        """La propiedad vencida debe ser False en el caso límite donde
        fecha_vencimiento == hoy. El modelo usa el operador '<', no '<='."""
        m = Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=9,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy,
            pagada=False,
        )
        self.assertFalse(m.vencida)


# ═══════════════════════════════════════════════════════════════
# FASE 2 — Restricciones de Mensualidad
# ═══════════════════════════════════════════════════════════════

class Fase2_RestriccionesMensualidadTestCase(TestCase):
    """Valida la constraint unique_together de Mensualidad:
    (atleta, periodo_mes, periodo_anio)."""

    def setUp(self):
        self.atleta = crear_atleta()
        self.hoy = timezone.now().date()

    def test_duplicado_mismo_atleta_mismo_periodo_lanza_integrity_error(self):
        """No se pueden crear dos mensualidades para el mismo atleta
        en el mismo período (mes + año). Debe lanzar IntegrityError."""
        Mensualidad.objects.create(
            atleta=self.atleta,
            periodo_mes=5,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Mensualidad.objects.create(
                    atleta=self.atleta,
                    periodo_mes=5,
                    periodo_anio=2026,
                    monto_usd=Decimal('10.00'),
                    fecha_vencimiento=self.hoy + timedelta(days=30),
                )

    def test_mismo_periodo_atletas_diferentes_sin_error(self):
        """Sí se pueden crear dos mensualidades del mismo período
        para atletas DIFERENTES sin violar la constraint."""
        rep_a = crear_representante(cedula='V11111111', correo='a@test.com')
        cat_a = crear_categoria(nombre='Sub-10')
        atleta_a = crear_atleta(representante=rep_a, categoria=cat_a)

        rep_b = crear_representante(cedula='V22222222', correo='b@test.com')
        cat_b = crear_categoria(nombre='Sub-11')
        atleta_b = crear_atleta(representante=rep_b, categoria=cat_b)

        Mensualidad.objects.create(
            atleta=atleta_a,
            periodo_mes=5,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        Mensualidad.objects.create(
            atleta=atleta_b,
            periodo_mes=5,
            periodo_anio=2026,
            monto_usd=Decimal('10.00'),
            fecha_vencimiento=self.hoy + timedelta(days=30),
        )
        self.assertEqual(Mensualidad.objects.count(), 2)


# ═══════════════════════════════════════════════════════════════
# FASE 3 — Cálculo automático de monto_usd en Pago.save()
# ═══════════════════════════════════════════════════════════════

class Fase3_CalculoMontoUSDPagoTestCase(TestCase):
    """Valida que Pago.save() calcula monto_usd = monto_bs / tasa_bcv
    con redondeo ROUND_HALF_UP a 2 decimales."""

    def setUp(self):
        self.representante = crear_representante()

    def test_division_exacta_sin_redondeo(self):
        """Cuando monto_bs=100.00 y tasa_bcv=50.0000, el resultado es
        exactamente 2.00 sin necesidad de redondeo."""
        pago = _crear_pago_base(
            self.representante,
            monto_bs=Decimal('100.00'),
            tasa_bcv=Decimal('50.0000'),
            referencia='REF-F3-01',
        )
        self.assertEqual(pago.monto_usd, Decimal('2.00'))

    def test_redondeo_half_up_hacia_arriba(self):
        """Cuando 100.00 / 35.55 = 2.8129..., el redondeo HALF_UP
        debe producir 2.81."""
        pago = _crear_pago_base(
            self.representante,
            monto_bs=Decimal('100.00'),
            tasa_bcv=Decimal('35.5500'),
            referencia='REF-F3-02',
        )
        self.assertEqual(pago.monto_usd, Decimal('2.81'))

    def test_redondeo_half_up_en_limite_exacto_punto_cinco(self):
        """Cuando 281.00 / 200.00 = 1.405 exacto, el redondeo HALF_UP
        debe producir 1.41, no 1.40 (lo que haría ROUND_HALF_EVEN).
        Usamos valores con 2 decimales para evitar que DecimalField(decimal_places=2)
        cuantice el monto_bs antes de la división."""
        pago = _crear_pago_base(
            self.representante,
            monto_bs=Decimal('281.00'),
            tasa_bcv=Decimal('200.0000'),
            referencia='REF-F3-03',
        )
        self.assertEqual(pago.monto_usd, Decimal('1.41'))

    def test_monto_usd_none_cuando_tasa_bcv_es_none(self):
        """Si tasa_bcv es None, el save() no debe calcular monto_usd
        y este debe permanecer como None."""
        pago = _crear_pago_base(
            self.representante,
            monto_bs=Decimal('100.00'),
            tasa_bcv=None,
            monto_usd=None,
            referencia='REF-F3-04',
        )
        self.assertIsNone(pago.monto_usd)


# ═══════════════════════════════════════════════════════════════
# FASE 4 — Cálculo automático de comprobante_hash en Pago.save()
# ═══════════════════════════════════════════════════════════════

class Fase4_HashComprobantePagoTestCase(TestCase):
    """Valida que Pago.save() genera un hash SHA-256 del comprobante
    cuando este existe y el hash está vacío."""

    def setUp(self):
        self.representante = crear_representante()

    def test_hash_sha256_se_genera_al_crear_pago(self):
        """Al crear un pago con comprobante, se genera un hash SHA-256
        de exactamente 64 caracteres hexadecimales (0-9, a-f)."""
        comprobante = SimpleUploadedFile(
            'prueba.pdf', b'contenido_de_prueba',
            content_type='application/pdf',
        )
        pago = _crear_pago_base(
            self.representante,
            comprobante=comprobante,
            referencia='REF-F4-01',
        )
        self.assertEqual(len(pago.comprobante_hash), 64)
        self.assertRegex(pago.comprobante_hash, r'^[0-9a-f]{64}$')

    def test_mismo_contenido_produce_mismo_hash(self):
        """Dos archivos con contenido idéntico deben producir el mismo
        hash SHA-256, independientemente del nombre del archivo."""
        contenido = b'mismo_contenido'
        pago1 = _crear_pago_base(
            self.representante,
            comprobante=SimpleUploadedFile('a.pdf', contenido, content_type='application/pdf'),
            referencia='REF-F4-02A',
        )
        rep2 = crear_representante(cedula='V99999998', correo='rep2@test.com')
        pago2 = _crear_pago_base(
            rep2,
            comprobante=SimpleUploadedFile('b.pdf', contenido, content_type='application/pdf'),
            referencia='REF-F4-02B',
        )
        self.assertEqual(pago1.comprobante_hash, pago2.comprobante_hash)

    def test_contenido_diferente_produce_hash_diferente(self):
        """Dos archivos con contenido diferente deben producir hashes
        SHA-256 distintos."""
        pago1 = _crear_pago_base(
            self.representante,
            comprobante=SimpleUploadedFile('a.pdf', b'contenido_A', content_type='application/pdf'),
            referencia='REF-F4-03A',
        )
        rep2 = crear_representante(cedula='V99999997', correo='rep3@test.com')
        pago2 = _crear_pago_base(
            rep2,
            comprobante=SimpleUploadedFile('b.pdf', b'contenido_B', content_type='application/pdf'),
            referencia='REF-F4-03B',
        )
        self.assertNotEqual(pago1.comprobante_hash, pago2.comprobante_hash)

    def test_hash_no_se_recalcula_al_guardar_de_nuevo(self):
        """Si el pago se guarda dos veces sin cambiar el archivo,
        el hash no debe recalcularse (la condición es 'not comprobante_hash')."""
        pago = _crear_pago_base(
            self.representante,
            comprobante=SimpleUploadedFile('doc.pdf', b'contenido_fijo', content_type='application/pdf'),
            referencia='REF-F4-04',
        )
        hash_inicial = pago.comprobante_hash
        pago.motivo_rechazo = 'Motivo de prueba'
        pago.save()
        self.assertEqual(pago.comprobante_hash, hash_inicial)


# ═══════════════════════════════════════════════════════════════
# FASE 5 — Constraint de unicidad de referencia bancaria
# ═══════════════════════════════════════════════════════════════

class Fase5_ConstraintsReferenciaPagoTestCase(TestCase):
    """Valida la UniqueConstraint 'uniq_referencia_activa' que impide
    duplicados de (banco_emisor, referencia) cuando el estado es
    PENDIENTE o APROBADO."""

    def setUp(self):
        self.representante = crear_representante()

    def test_dos_pendientes_misma_referencia_lanza_integrity_error(self):
        """Dos pagos PENDIENTES con la misma combinación (banco_emisor,
        referencia) deben violar la constraint y lanzar IntegrityError."""
        _crear_pago_base(
            self.representante,
            banco_emisor='0102',
            referencia='REF001',
            estado='PENDIENTE',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _crear_pago_base(
                    self.representante,
                    banco_emisor='0102',
                    referencia='REF001',
                    estado='PENDIENTE',
                )

    def test_pendiente_y_aprobado_misma_referencia_lanza_integrity_error(self):
        """Un pago APROBADO y uno PENDIENTE con la misma referencia
        también deben violar la constraint y lanzar IntegrityError."""
        _crear_pago_base(
            self.representante,
            banco_emisor='0102',
            referencia='REF002',
            estado='APROBADO',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _crear_pago_base(
                    self.representante,
                    banco_emisor='0102',
                    referencia='REF002',
                    estado='PENDIENTE',
                )

    def test_rechazado_permite_reutilizar_referencia(self):
        """Tras un RECHAZO, la misma referencia SÍ se puede reutilizar
        en un nuevo pago PENDIENTE, porque el constraint solo aplica
        a estados PENDIENTE y APROBADO."""
        _crear_pago_base(
            self.representante,
            banco_emisor='0102',
            referencia='REF003',
            estado='RECHAZADO',
        )
        pago_nuevo = _crear_pago_base(
            self.representante,
            banco_emisor='0102',
            referencia='REF003',
            estado='PENDIENTE',
        )
        self.assertEqual(pago_nuevo.estado, 'PENDIENTE')

    def test_misma_referencia_bancos_diferentes_sin_conflicto(self):
        """La misma referencia en bancos DIFERENTES no genera conflicto,
        porque la constraint incluye banco_emisor en la combinación."""
        _crear_pago_base(
            self.representante,
            banco_emisor='0102',
            referencia='REF004',
            estado='PENDIENTE',
        )
        pago_b = _crear_pago_base(
            self.representante,
            banco_emisor='0134',
            referencia='REF004',
            estado='PENDIENTE',
        )
        self.assertEqual(pago_b.estado, 'PENDIENTE')
