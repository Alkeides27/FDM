import pytest
from datetime import date, timedelta
from django.urls import reverse
from django.utils import timezone
from deportivo.models import Partido, Estadistica


@pytest.mark.integration
def test_gestion_deportiva_puede_crear_partido_programado(
    client_coord_general, categoria
):
    """POST a partido_create crea Partido con procesado=False."""
    url = reverse('partido_create')
    fecha = timezone.now() + timedelta(days=7)
    data = {
        'categoria': categoria.id,
        'fecha_hora': fecha.strftime('%Y-%m-%dT%H:%M'),
        'equipo_rival': 'Deportivo Lara',
        'tipo': 'AMISTOSO',
        'condicion': 'CASA',
    }
    response = client_coord_general.post(url, data)
    assert response.status_code == 302
    partido = Partido.objects.latest('id')
    assert partido.procesado is False
    assert partido.equipo_rival == 'Deportivo Lara'


@pytest.mark.integration
def test_registrar_resultado_marca_partido_como_procesado(
    client_coord_general, categoria, atleta_de
):
    """POST con resultado actualiza procesado=True."""
    partido = Partido.objects.create(
        categoria=categoria,
        fecha_hora=timezone.now(),
        equipo_rival='Deportivo Lara',
        tipo='AMISTOSO',
        condicion='CASA'
    )
    url = reverse('partido_resultado', args=[partido.id])
    data = {
        'goles_favor_escuela': '2',
        'goles_contra_rival': '1',
        'estadisticas-TOTAL_FORMS': '1',
        'estadisticas-INITIAL_FORMS': '0',
        'estadisticas-MIN_NUM_FORMS': '0',
        'estadisticas-MAX_NUM_FORMS': '1000',
        'estadisticas-0-goles': '2',
        'estadisticas-0-asistencias': '1',
        'estadisticas-0-tarjetas_amarillas': '0',
        'estadisticas-0-tarjetas_rojas': '0',
        'estadisticas-0-calificacion_dt': '7',
        'estadisticas-0-es_titular': 'on',
    }
    response = client_coord_general.post(url, data)
    assert response.status_code == 302
    partido.refresh_from_db()
    assert partido.procesado is True


@pytest.mark.integration
def test_registrar_resultado_calcula_goles_totales_desde_estadisticas(
    client_coord_general, categoria, atleta_de
):
    """partido.goles_favor_escuela es la suma de goles de estadísticas."""
    # Crear un segundo atleta para tener múltiples estadísticas en el formset
    from django.contrib.auth.models import User
    from filiacion.models import Representante, Atleta
    otro_user = User.objects.create_user(username='otherrep4', password='ClaveSegura123!')
    otro_rep = Representante.objects.create(
        cedula_identidad='22222225', nombres='Otro', apellidos='Rep',
        telefono_principal='04141112233', direccion_habitacion='Caracas',
        correo_electronico='other4@test.com', usuario=otro_user
    )
    atleta2 = Atleta.objects.create(
        representante=otro_rep, categoria=categoria,
        nombres='Juan', apellidos='Gomez',
        fecha_nacimiento=date(2017, 5, 20),
        lateralidad='DERECHO', posicion='DEL'
    )

    partido = Partido.objects.create(
        categoria=categoria,
        fecha_hora=timezone.now(),
        equipo_rival='Deportivo Lara',
        tipo='AMISTOSO',
        condicion='CASA'
    )
    url = reverse('partido_resultado', args=[partido.id])
    data = {
        'goles_favor_escuela': '0',  # Debe ser sobrescrita
        'goles_contra_rival': '1',
        'estadisticas-TOTAL_FORMS': '2',
        'estadisticas-INITIAL_FORMS': '0',
        'estadisticas-MIN_NUM_FORMS': '0',
        'estadisticas-MAX_NUM_FORMS': '1000',
        
        'estadisticas-0-goles': '2',
        'estadisticas-0-asistencias': '0',
        'estadisticas-0-tarjetas_amarillas': '0',
        'estadisticas-0-tarjetas_rojas': '0',
        'estadisticas-0-calificacion_dt': '7',
        'estadisticas-0-es_titular': 'on',
        
        'estadisticas-1-goles': '1',
        'estadisticas-1-asistencias': '1',
        'estadisticas-1-tarjetas_amarillas': '0',
        'estadisticas-1-tarjetas_rojas': '0',
        'estadisticas-1-calificacion_dt': '8',
        'estadisticas-1-es_titular': 'on',
    }
    client_coord_general.post(url, data)
    partido.refresh_from_db()
    assert partido.goles_favor_escuela == 3


@pytest.mark.integration
def test_registrar_resultado_asigna_victoria_cuando_goles_favor_mayores(
    client_coord_general, categoria, atleta_de
):
    """Con goles a favor > goles contra -> resultado='VICTORIA'."""
    partido = Partido.objects.create(
        categoria=categoria,
        fecha_hora=timezone.now(),
        equipo_rival='Deportivo Lara',
        tipo='AMISTOSO',
        condicion='CASA'
    )
    url = reverse('partido_resultado', args=[partido.id])
    data = {
        'goles_favor_escuela': '2',
        'goles_contra_rival': '1',
        'estadisticas-TOTAL_FORMS': '1',
        'estadisticas-INITIAL_FORMS': '0',
        'estadisticas-MIN_NUM_FORMS': '0',
        'estadisticas-MAX_NUM_FORMS': '1000',
        'estadisticas-0-goles': '2',
        'estadisticas-0-asistencias': '1',
        'estadisticas-0-tarjetas_amarillas': '0',
        'estadisticas-0-tarjetas_rojas': '0',
        'estadisticas-0-calificacion_dt': '7',
        'estadisticas-0-es_titular': 'on',
    }
    client_coord_general.post(url, data)
    partido.refresh_from_db()
    assert partido.resultado == 'VICTORIA'


@pytest.mark.integration
def test_partido_procesado_no_se_puede_volver_a_editar(
    client_coord_general, categoria
):
    """GET a partido_registrar_resultado con partido ya procesado -> redirect."""
    partido = Partido.objects.create(
        categoria=categoria,
        fecha_hora=timezone.now(),
        equipo_rival='Deportivo Lara',
        tipo='AMISTOSO',
        condicion='CASA',
        procesado=True,
        resultado='VICTORIA'
    )
    url = reverse('partido_resultado', args=[partido.id])
    response = client_coord_general.get(url)
    assert response.status_code == 302
    assert response.url == reverse('partido_list')
