import pytest
from datetime import date
from django.urls import reverse
from deportivo.models import EvaluacionTecnica, EvaluacionPsicosocial
from administracion.models import Entrenador, Coordinador


@pytest.mark.integration
def test_entrenador_puede_crear_evaluacion_tecnica(
    client_entrenador, atleta_de
):
    """POST como Entrenador crea EvaluacionTecnica."""
    # Crear un entrenador de base
    ent = Entrenador.objects.create(
        nombres='Carlos', apellidos='Entrena',
        licencia='FVF', telefono='04141234567'
    )
    url = reverse('evaluacion_tecnica_create')
    data = {
        'atleta': atleta_de.id,
        'entrenador': ent.id,
        'fecha_evaluacion': '2026-06-08',
        'velocidad': '5',
        'resistencia': '6',
        'control_balon': '7',
        'pase_corto': '8',
        'tiro': '9',
        'inteligencia_tactica': '10',
        'observaciones': 'Buen desempeño.'
    }
    response = client_entrenador.post(url, data)
    assert response.status_code == 302
    assert EvaluacionTecnica.objects.count() == 1


@pytest.mark.integration
def test_evaluacion_tecnica_vincula_correctamente_atleta_y_entrenador(
    client_entrenador, atleta_de
):
    """FK atleta y entrenador quedan asignados."""
    ent = Entrenador.objects.create(
        nombres='Carlos', apellidos='Entrena',
        licencia='FVF', telefono='04141234567'
    )
    url = reverse('evaluacion_tecnica_create')
    data = {
        'atleta': atleta_de.id,
        'entrenador': ent.id,
        'fecha_evaluacion': '2026-06-08',
        'velocidad': '5',
        'resistencia': '5',
        'control_balon': '5',
        'pase_corto': '5',
        'tiro': '5',
        'inteligencia_tactica': '5',
        'observaciones': ''
    }
    client_entrenador.post(url, data)
    eval_t = EvaluacionTecnica.objects.latest('id')
    assert eval_t.atleta == atleta_de
    assert eval_t.entrenador == ent


@pytest.mark.integration
def test_coord_deportivo_puede_crear_evaluacion_psicosocial(
    client_coord_general, coord_general, atleta_de
):
    """POST como CoordinadorGeneral/Deportivo crea EvaluacionPsicosocial."""
    coord_profile = Coordinador.objects.create(
        usuario_sistema=coord_general,
        nombres='Maria', apellidos='Coordina',
        cargo='DEPORTIVO'
    )
    url = reverse('evaluacion_psicosocial_create')
    data = {
        'atleta': atleta_de.id,
        'coordinador_evaluador': coord_profile.id,
        'fecha_evaluacion': '2026-06-08',
        'compromiso': '7',
        'puntualidad': '8',
        'companerismo': '9',
        'respeto': '10',
        'manejo_frustracion': '6',
        'observaciones_conductuales': 'Muy receptivo.'
    }
    response = client_coord_general.post(url, data)
    assert response.status_code == 302
    assert EvaluacionPsicosocial.objects.count() == 1


@pytest.mark.integration
def test_representante_no_puede_crear_evaluaciones(
    client_representante, atleta_de
):
    """POST como representante -> 403."""
    url = reverse('evaluacion_tecnica_create')
    response = client_representante.post(url, {})
    assert response.status_code == 403
