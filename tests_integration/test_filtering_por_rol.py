import pytest
from datetime import date
from django.urls import reverse
from django.contrib.auth.models import User
from filiacion.models import Representante, Atleta


@pytest.mark.integration
def test_representante_solo_ve_sus_propios_atletas_en_lista(
    client_representante, representante_con_user, atleta_de, categoria
):
    """GET /atletas/ como representante -> solo sus atletas."""
    # Crear otro representante y su atleta
    otro_user = User.objects.create_user(username='otherrep', password='ClaveSegura123!')
    otro_rep = Representante.objects.create(
        cedula_identidad='22222222', nombres='Otro', apellidos='Rep',
        telefono_principal='04141112233', direccion_habitacion='Caracas',
        correo_electronico='other@test.com', usuario=otro_user
    )
    otro_atleta = Atleta.objects.create(
        representante=otro_rep, categoria=categoria,
        nombres='Ajeno', apellidos='Atleta',
        fecha_nacimiento=date(2017, 5, 20),
        lateralidad='DERECHO', posicion='DEL'
    )

    url = reverse('atleta_list')
    response = client_representante.get(url)
    assert response.status_code == 200
    
    atletas = response.context['atletas']
    assert atleta_de in atletas
    assert otro_atleta not in atletas


@pytest.mark.integration
def test_representante_no_puede_ver_atleta_de_otro_representante(
    client_representante, categoria
):
    """GET /atletas/<pk_ajeno>/ como representante -> 403."""
    otro_user = User.objects.create_user(username='otherrep2', password='ClaveSegura123!')
    otro_rep = Representante.objects.create(
        cedula_identidad='22222223', nombres='Otro', apellidos='Rep',
        telefono_principal='04141112233', direccion_habitacion='Caracas',
        correo_electronico='other2@test.com', usuario=otro_user
    )
    otro_atleta = Atleta.objects.create(
        representante=otro_rep, categoria=categoria,
        nombres='Ajeno', apellidos='Atleta',
        fecha_nacimiento=date(2017, 5, 20),
        lateralidad='DERECHO', posicion='DEL'
    )

    url = reverse('atleta_detail', args=[otro_atleta.id])
    response = client_representante.get(url)
    assert response.status_code == 403


@pytest.mark.integration
def test_staff_interno_ve_todos_los_atletas_en_lista(
    client_tesorero, representante_con_user, atleta_de, categoria
):
    """GET /atletas/ como tesorero -> ve atletas de todos los representantes."""
    otro_user = User.objects.create_user(username='otherrep3', password='ClaveSegura123!')
    otro_rep = Representante.objects.create(
        cedula_identidad='22222224', nombres='Otro', apellidos='Rep',
        telefono_principal='04141112233', direccion_habitacion='Caracas',
        correo_electronico='other3@test.com', usuario=otro_user
    )
    otro_atleta = Atleta.objects.create(
        representante=otro_rep, categoria=categoria,
        nombres='Ajeno', apellidos='Atleta',
        fecha_nacimiento=date(2017, 5, 20),
        lateralidad='DERECHO', posicion='DEL'
    )

    url = reverse('atleta_list')
    response = client_tesorero.get(url)
    assert response.status_code == 200
    
    atletas = response.context['atletas']
    assert atleta_de in atletas
    assert otro_atleta in atletas


@pytest.mark.integration
def test_representante_no_puede_crear_atleta(
    client_representante
):
    """POST /atletas/crear/ como representante -> 403."""
    url = reverse('atleta_create')
    response = client_representante.post(url, {})
    assert response.status_code == 403


@pytest.mark.integration
def test_coord_general_puede_crear_atleta(
    client_coord_general, representante_con_user, categoria
):
    """POST con datos válidos como CoordinadorGeneral -> 302 a detalle."""
    url = reverse('atleta_create')
    data = {
        'representante': representante_con_user.id,
        'categoria': categoria.id,
        'nombres': 'Pedro',
        'apellidos': 'Gomez',
        'fecha_nacimiento': '2017-03-15',
        'lateralidad': 'DERECHO',
        'posicion': 'DEL',
        'activo': True,
        'becado': False,
    }
    response = client_coord_general.post(url, data)
    assert response.status_code == 302
    assert Atleta.objects.filter(nombres='Pedro', apellidos='Gomez').exists()


@pytest.mark.integration
def test_anonimo_es_redirigido_a_login_al_acceder_atletas(
    client
):
    """GET /atletas/ sin login -> 302 a login."""
    url = reverse('atleta_list')
    response = client.get(url)
    assert response.status_code == 302
