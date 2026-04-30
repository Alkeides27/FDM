# finanzas/models.py
import hashlib
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# === Choices ===
ESTADO_PAGO_CHOICES = [
    ('PENDIENTE', 'Pendiente'),
    ('APROBADO',  'Aprobado'),
    ('RECHAZADO', 'Rechazado'),
]

METODO_PAGO_CHOICES = [
    ('PAGO_MOVIL',     'Pago Móvil'),
    ('TRANSFERENCIA',  'Transferencia'),
    ('EFECTIVO_BS',    'Efectivo Bs'),
    ('EFECTIVO_USD',   'Efectivo USD'),
    ('OTRO',           'Otro'),
]

BANCO_CHOICES = [
    ('0102', 'Banco de Venezuela'),
    ('0105', 'Mercantil'),
    ('0108', 'BBVA Provincial'),
    ('0114', 'Bancaribe'),
    ('0134', 'Banesco'),
    ('0151', 'BFC Banco Fondo Común'),
    ('0156', '100% Banco'),
    ('0163', 'Banco del Tesoro'),
    ('0172', 'Bancamiga'),
    ('0174', 'Banplus'),
    ('0175', 'Bicentenario'),
    ('0191', 'BNC Nacional de Crédito'),
    ('OTRO', 'Otro'),
]

ACCION_AUDIT_CHOICES = [
    ('CREADO',          'Creado'),
    ('APROBADO',        'Aprobado'),
    ('RECHAZADO',       'Rechazado'),
    ('EDITADO',         'Editado'),
    ('ANULADO',         'Anulado'),
    ('MENSUALIDADES_VINCULADAS', 'Mensualidades vinculadas'),
]

TIPO_ENTE_PATROCINANTE_CHOICES = [
    ('PUBLICO', 'Público'),
    ('PRIVADO', 'Privado'),
    ('ONG', 'ONG'),
]

TIPO_APORTE_CHOICES = [
    ('MONETARIO', 'Monetario'),
    ('INSUMOS', 'Insumos'),
]


# === Modelo TasaBCV (cache local) ===
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


# === Modelo Mensualidad ===
class Mensualidad(models.Model):
    """Cada mensualidad que un atleta debe pagar. Una fila por mes por atleta."""
    atleta = models.ForeignKey(
        'filiacion.Atleta', on_delete=models.CASCADE, related_name='mensualidades'
    )
    periodo_mes = models.IntegerField(help_text="1-12")
    periodo_anio = models.IntegerField(help_text="Ej: 2026")
    monto_usd = models.DecimalField(
        max_digits=8, decimal_places=2,
        help_text="Monto base en USD"
    )
    fecha_vencimiento = models.DateField()
    pagada = models.BooleanField(default=False, db_index=True)
    pago = models.ForeignKey(
        'Pago', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='mensualidades_cubiertas',
        help_text="Pago que cubrió esta mensualidad"
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('atleta', 'periodo_mes', 'periodo_anio')]
        indexes = [
            models.Index(fields=['pagada', 'fecha_vencimiento']),
            models.Index(fields=['atleta', 'pagada']),
        ]
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f"{self.atleta} - {self.periodo_mes}/{self.periodo_anio}"

    @property
    def vencida(self):
        return not self.pagada and self.fecha_vencimiento < timezone.now().date()

    @property
    def etiqueta_periodo(self):
        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return f"{meses[self.periodo_mes - 1]} {self.periodo_anio}"


# === Modelo Pago ===
class Pago(models.Model):
    representante = models.ForeignKey(
        'filiacion.Representante', on_delete=models.PROTECT, related_name='pagos'
    )
    concepto = models.CharField(
        max_length=200,
        help_text="Auto-generado desde mensualidades cubiertas, o texto libre"
    )

    metodo = models.CharField(max_length=15, choices=METODO_PAGO_CHOICES)
    banco_emisor = models.CharField(max_length=4, choices=BANCO_CHOICES, blank=True)
    referencia = models.CharField(max_length=30, blank=True, db_index=True)

    monto_bs = models.DecimalField(max_digits=14, decimal_places=2)
    tasa_bcv = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    monto_usd = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    fecha_pago = models.DateField()
    fecha_reporte = models.DateTimeField(auto_now_add=True)

    comprobante = models.FileField(upload_to='pagos/%Y/%m/')
    comprobante_hash = models.CharField(max_length=64, blank=True, db_index=True)

    estado = models.CharField(
        max_length=10, choices=ESTADO_PAGO_CHOICES, default='PENDIENTE'
    )
    motivo_rechazo = models.TextField(blank=True)

    revisado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True,
        related_name='pagos_revisados'
    )
    revisado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_reporte']
        constraints = [
            models.UniqueConstraint(
                fields=['banco_emisor', 'referencia'],
                condition=models.Q(estado__in=['PENDIENTE', 'APROBADO']),
                name='uniq_referencia_activa'
            ),
        ]

    def save(self, *args, **kwargs):
        if self.comprobante and not self.comprobante_hash:
            self.comprobante_hash = self._calcular_hash()
        if self.monto_bs and self.tasa_bcv:
            self.monto_usd = self.monto_bs / self.tasa_bcv
        super().save(*args, **kwargs)

    def _calcular_hash(self):
        sha = hashlib.sha256()
        for chunk in self.comprobante.chunks():
            sha.update(chunk)
        self.comprobante.seek(0)
        return sha.hexdigest()

    def registrar_audit(self, accion, actor=None, estado_anterior='', estado_nuevo='', detalles=None):
        """Helper para registrar entradas en el audit log."""
        PagoAuditLog.objects.create(
            pago=self,
            accion=accion,
            actor=actor,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            detalles=detalles or {}
        )

    def __str__(self):
        return f"Pago #{self.id} - {self.representante} - {self.estado}"


# === Modelo PagoAuditLog ===
class PagoAuditLog(models.Model):
    """Registro inmutable de cada cambio sobre un pago. Append-only."""
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE, related_name='audit_log')
    accion = models.CharField(max_length=30, choices=ACCION_AUDIT_CHOICES)
    estado_anterior = models.CharField(max_length=15, blank=True)
    estado_nuevo = models.CharField(max_length=15, blank=True)
    actor = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True,
        related_name='pagos_audit'
    )
    detalles = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['pago', '-timestamp'])]

    def __str__(self):
        return f"[{self.timestamp}] {self.accion} pago #{self.pago_id}"


# === Modelos preexistentes (preservar) ===
class Patrocinante(models.Model):
    nombre_empresa = models.CharField(max_length=200)
    tipo_ente = models.CharField(max_length=10, choices=TIPO_ENTE_PATROCINANTE_CHOICES)
    persona_contacto = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre_empresa


class Aporte(models.Model):
    patrocinante = models.ForeignKey(Patrocinante, on_delete=models.CASCADE, related_name='aportes')
    fecha_aporte = models.DateField()
    tipo = models.CharField(max_length=10, choices=TIPO_APORTE_CHOICES)
    descripcion = models.TextField()
    valor_estimado_usd = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Aporte de {self.patrocinante} ({self.fecha_aporte})"