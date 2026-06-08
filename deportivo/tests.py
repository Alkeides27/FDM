# deportivo/tests.py
# Pruebas unitarias — Módulo Deportivo
# PRD v1.0 | IngeniumCode-FDM | 8 de junio de 2026

from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from filiacion.models import Representante, Atleta
from administracion.models import Categoria
from deportivo.models import (
    Partido, Estadistica,
    EvaluacionTecnica, EvaluacionPsicosocial,
    Puntuacion,
)


# ═══════════════════════════════════════════════════════════════
# Helpers de fábrica
# ═══════════════════════════════════════════════════════════════

def crear_representante(cedula='12345678', correo='rep@test.com'):
    """Crea un Representante mínimo válido."""
    return Representante.objects.create(
        cedula_identidad=cedula,
        nombres='Juan', apellidos='Pérez',
        telefono_principal='04141234567',
        direccion_habitacion='Calle de prueba',
        correo_electronico=correo,
    )


def crear_categoria(nombre='Sub-9', genero='MASCULINO'):
    """Crea una Categoria con campos obligatorios."""
    categoria, _ = Categoria.objects.get_or_create(
        nombre=nombre,
        defaults={
            'anio_nacimiento_min': 2017,
            'anio_nacimiento_max': 2018,
            'genero': genero,
        }
    )
    return categoria


def crear_atleta(representante=None, categoria=None):
    """Crea un Atleta mínimo válido."""
    if representante is None:
        representante = crear_representante()
    if categoria is None:
        categoria = crear_categoria()
    return Atleta.objects.create(
        representante=representante, categoria=categoria,
        nombres='Pedro', apellidos='Pérez',
        fecha_nacimiento=date(2017, 3, 15),
        lateralidad='DERECHO', posicion='DEL',
    )


def crear_partido(categoria=None, equipo_rival='Rival FC',
                  tipo='AMISTOSO', condicion='CASA',
                  fecha_hora=None):
    """Crea un Partido programado (sin resultado, no procesado)."""
    if categoria is None:
        categoria = crear_categoria()
    return Partido.objects.create(
        categoria=categoria,
        fecha_hora=fecha_hora or timezone.now() + timedelta(days=7),
        equipo_rival=equipo_rival,
        tipo=tipo, condicion=condicion,
    )


def crear_estadistica(atleta=None, partido=None, **overrides):
    """Crea una Estadistica con valores razonables."""
    if atleta is None:
        atleta = crear_atleta()
    if partido is None:
        partido = crear_partido()
    defaults = {
        'atleta': atleta, 'partido': partido,
        'es_titular': False, 'minutos_jugados': 0,
        'goles': 0, 'asistencias': 0,
        'tarjetas_amarillas': 0, 'tarjetas_rojas': 0,
        'calificacion_dt': 5,
    }
    defaults.update(overrides)
    return Estadistica.objects.create(**defaults)


def calcular_resultado(goles_favor, goles_contra):
    """Replica la lógica de partido_registrar_resultado.
    Retorna 'VICTORIA', 'EMPATE' o 'DERROTA'."""
    if goles_favor > goles_contra:
        return 'VICTORIA'
    elif goles_favor < goles_contra:
        return 'DERROTA'
    else:
        return 'EMPATE'


# ═══════════════════════════════════════════════════════════════
# FASE 1 — Modelo Partido
# ═══════════════════════════════════════════════════════════════

class Fase1_PartidoTestCase(TestCase):
    """Valida la creación, strings y cascada del modelo Partido."""

    def test_partido_se_crea_con_defaults_correctos(self):
        """Un Partido nuevo debe tener goles en 0, procesado=False y resultado vacío."""
        categoria = crear_categoria()
        partido = crear_partido(categoria=categoria)
        self.assertEqual(partido.goles_favor_escuela, 0)
        self.assertEqual(partido.goles_contra_rival, 0)
        self.assertFalse(partido.procesado)
        self.assertEqual(partido.resultado, '')

    def test_partido_str_incluye_rival_y_fecha(self):
        """El método __str__ del Partido debe retornar 'Partido vs <rival> el <fecha>'."""
        fecha = timezone.now() + timedelta(days=7)
        partido = crear_partido(equipo_rival='Caracas FC', fecha_hora=fecha)
        self.assertEqual(str(partido), f"Partido vs Caracas FC el {fecha.date()}")

    def test_partido_acepta_tipo_amistoso_y_oficial(self):
        """El modelo debe permitir guardar partidos con tipo AMISTOSO u OFICIAL."""
        partido_a = crear_partido(tipo='AMISTOSO')
        partido_o = crear_partido(categoria=crear_categoria('Sub-11'), tipo='OFICIAL')
        self.assertEqual(partido_a.tipo, 'AMISTOSO')
        self.assertEqual(partido_o.tipo, 'OFICIAL')

    def test_partido_acepta_condicion_casa_y_visitante(self):
        """El modelo debe permitir guardar partidos con condición CASA o VISITANTE."""
        partido_c = crear_partido(condicion='CASA')
        partido_v = crear_partido(categoria=crear_categoria('Sub-11'), condicion='VISITANTE')
        self.assertEqual(partido_c.condicion, 'CASA')
        self.assertEqual(partido_v.condicion, 'VISITANTE')

    def test_borrar_categoria_borra_sus_partidos_en_cascada(self):
        """on_delete=models.CASCADE: borrar una Categoria elimina todos sus partidos."""
        categoria = crear_categoria()
        crear_partido(categoria=categoria)
        crear_partido(categoria=categoria, equipo_rival='Otro FC')
        self.assertEqual(Partido.objects.filter(categoria=categoria).count(), 2)
        cat_id = categoria.id
        categoria.delete()
        self.assertEqual(Partido.objects.filter(categoria_id=cat_id).count(), 0)


# ═══════════════════════════════════════════════════════════════
# FASE 2 — Modelo Estadistica y restricciones
# ═══════════════════════════════════════════════════════════════

class Fase2_EstadisticaTestCase(TestCase):
    """Valida el modelo Estadistica, restricciones de unicidad y validadores de rango."""

    def test_estadistica_se_crea_con_datos_minimos_validos(self):
        """Una Estadistica con calificación válida debe crearse correctamente."""
        est = crear_estadistica(calificacion_dt=5)
        self.assertEqual(Estadistica.objects.count(), 1)
        self.assertEqual(est.calificacion_dt, 5)

    def test_estadistica_str_menciona_atleta_y_rival(self):
        """El método __str__ de Estadistica debe contener el atleta y el rival del partido."""
        atleta = crear_atleta()
        partido = crear_partido(equipo_rival='Zamora FC')
        est = crear_estadistica(atleta=atleta, partido=partido)
        self.assertEqual(str(est), f"Estadística de {atleta} en partido vs Zamora FC")

    def test_estadistica_duplicada_mismo_atleta_mismo_partido_lanza_integrity_error(self):
        """Un atleta no puede tener dos estadísticas en el mismo partido (unique_together)."""
        atleta = crear_atleta()
        partido = crear_partido()
        crear_estadistica(atleta=atleta, partido=partido, calificacion_dt=5)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                crear_estadistica(atleta=atleta, partido=partido, calificacion_dt=7)

    def test_estadistica_mismo_atleta_partidos_diferentes_sin_error(self):
        """El mismo atleta puede registrar estadísticas en diferentes partidos."""
        atleta = crear_atleta()
        partido1 = crear_partido(equipo_rival='Rival 1')
        partido2 = crear_partido(categoria=crear_categoria('Sub-11'), equipo_rival='Rival 2')
        est1 = crear_estadistica(atleta=atleta, partido=partido1)
        est2 = crear_estadistica(atleta=atleta, partido=partido2)
        self.assertEqual(Estadistica.objects.count(), 2)

    def test_calificacion_dt_fuera_de_rango_falla_full_clean(self):
        """calificacion_dt debe estar entre 1 y 10. Valor 15 debe lanzar ValidationError."""
        atleta = crear_atleta()
        partido = crear_partido()
        est = Estadistica(
            atleta=atleta, partido=partido,
            calificacion_dt=15,
        )
        with self.assertRaises(ValidationError):
            est.full_clean()

    def test_borrar_atleta_borra_sus_estadisticas_en_cascada(self):
        """on_delete=models.CASCADE: al borrar un Atleta se borran sus estadísticas en cascada."""
        atleta = crear_atleta()
        crear_estadistica(atleta=atleta)
        self.assertEqual(Estadistica.objects.filter(atleta=atleta).count(), 1)
        atleta_id = atleta.id
        atleta.delete()
        self.assertEqual(Estadistica.objects.filter(atleta_id=atleta_id).count(), 0)


# ═══════════════════════════════════════════════════════════════
# FASE 3 — Modelo EvaluacionTecnica
# ═══════════════════════════════════════════════════════════════

class Fase3_EvaluacionTecnicaTestCase(TestCase):
    """Valida la creación, formato y IntegerChoices de EvaluacionTecnica."""

    def test_evaluacion_tecnica_se_crea_con_puntuaciones_validas(self):
        """Una evaluación física con puntuaciones válidas debe crearse correctamente."""
        atleta = crear_atleta()
        eval_t = EvaluacionTecnica.objects.create(
            atleta=atleta,
            fecha_evaluacion=date.today(),
            velocidad=Puntuacion.CINCO,
            resistencia=Puntuacion.OCHO,
            control_balon=Puntuacion.DIEZ,
            pase_corto=Puntuacion.SIETE,
            tiro=Puntuacion.SEIS,
            inteligencia_tactica=Puntuacion.NUEVE,
        )
        self.assertEqual(EvaluacionTecnica.objects.count(), 1)
        self.assertEqual(eval_t.velocidad, 5)

    def test_evaluacion_tecnica_str_incluye_atleta_y_fecha(self):
        """El método __str__ de EvaluacionTecnica debe contener el nombre del atleta y la fecha."""
        atleta = crear_atleta()
        fecha = date.today()
        eval_t = EvaluacionTecnica.objects.create(
            atleta=atleta,
            fecha_evaluacion=fecha,
            velocidad=5, resistencia=5, control_balon=5,
            pase_corto=5, tiro=5, inteligencia_tactica=5,
        )
        self.assertEqual(str(eval_t), f"Evaluación Técnica de {atleta} ({fecha})")

    def test_evaluacion_tecnica_con_puntuacion_fuera_de_rango_falla_full_clean(self):
        """Puntuaciones fuera del set de choices válidos (1-10) deben fallar en full_clean."""
        atleta = crear_atleta()
        eval_t = EvaluacionTecnica(
            atleta=atleta,
            fecha_evaluacion=date.today(),
            velocidad=15,  # Fuera de rango
            resistencia=5, control_balon=5, pase_corto=5,
            tiro=5, inteligencia_tactica=5,
        )
        with self.assertRaises(ValidationError):
            eval_t.full_clean()

    def test_observaciones_son_opcionales(self):
        """El campo observaciones debe permitir estar vacío (blank=True) sin error."""
        atleta = crear_atleta()
        eval_t = EvaluacionTecnica.objects.create(
            atleta=atleta,
            fecha_evaluacion=date.today(),
            velocidad=5, resistencia=5, control_balon=5,
            pase_corto=5, tiro=5, inteligencia_tactica=5,
            observaciones='',
        )
        self.assertEqual(eval_t.observaciones, '')


# ═══════════════════════════════════════════════════════════════
# FASE 4 — Modelo EvaluacionPsicosocial
# ═══════════════════════════════════════════════════════════════

class Fase4_EvaluacionPsicosocialTestCase(TestCase):
    """Valida la creación y string de EvaluacionPsicosocial para confirmar su comportamiento."""

    def test_evaluacion_psicosocial_se_crea_con_puntuaciones_validas(self):
        """Una evaluación conductual con puntuaciones válidas debe crearse correctamente."""
        atleta = crear_atleta()
        eval_p = EvaluacionPsicosocial.objects.create(
            atleta=atleta,
            fecha_evaluacion=date.today(),
            compromiso=Puntuacion.SIETE,
            puntualidad=Puntuacion.NUEVE,
            companerismo=Puntuacion.DIEZ,
            respeto=Puntuacion.OCHO,
            manejo_frustracion=Puntuacion.SEIS,
        )
        self.assertEqual(EvaluacionPsicosocial.objects.count(), 1)
        self.assertEqual(eval_p.compromiso, 7)

    def test_evaluacion_psicosocial_str_menciona_atleta_y_fecha(self):
        """El método __str__ de EvaluacionPsicosocial debe contener el nombre del atleta y la fecha."""
        atleta = crear_atleta()
        fecha = date.today()
        eval_p = EvaluacionPsicosocial.objects.create(
            atleta=atleta,
            fecha_evaluacion=fecha,
            compromiso=5, puntualidad=5, companerismo=5,
            respeto=5, manejo_frustracion=5,
        )
        self.assertEqual(str(eval_p), f"Evaluación Psicosocial de {atleta} ({fecha})")


# ═══════════════════════════════════════════════════════════════
# FASE 5 — Lógica de cálculo de resultado del partido
# ═══════════════════════════════════════════════════════════════

class Fase5_CalcularResultadoPartidoTestCase(TestCase):
    """Prueba la lógica pura de negocio para el cálculo de resultados de partidos."""

    def test_calcular_resultado_con_goles_favor_mayores_retorna_victoria(self):
        """Si los goles a favor de la escuela superan los del rival, debe retornar VICTORIA."""
        self.assertEqual(calcular_resultado(3, 1), 'VICTORIA')

    def test_calcular_resultado_con_goles_contra_mayores_retorna_derrota(self):
        """Si los goles del rival superan a los de la escuela, debe retornar DERROTA."""
        self.assertEqual(calcular_resultado(1, 4), 'DERROTA')

    def test_calcular_resultado_con_goles_iguales_retorna_empate(self):
        """Si los goles de ambos equipos son iguales y mayores que cero, debe retornar EMPATE."""
        self.assertEqual(calcular_resultado(2, 2), 'EMPATE')

    def test_calcular_resultado_con_ambos_cero_retorna_empate(self):
        """Si ambos equipos quedan en cero goles, debe retornar EMPATE."""
        self.assertEqual(calcular_resultado(0, 0), 'EMPATE')

    def test_calcular_resultado_con_diferencia_minima_de_un_gol_a_favor_retorna_victoria(self):
        """Una diferencia mínima a favor (ej: 2 a 1) debe ser identificada como VICTORIA."""
        self.assertEqual(calcular_resultado(2, 1), 'VICTORIA')
