from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from .models import Atleta, Representante
from .forms import AtletaForm, RepresentanteForm
from .utils import generar_ficha_tecnica_pdf

# --- Atletas ---


@login_required
def atleta_list(request):
    atletas = Atleta.objects.all().order_by('apellidos')
    return render(request, 'filiacion/atleta_list.html', {'atletas': atletas})


@login_required
def atleta_detail(request, pk):
    atleta = get_object_or_404(Atleta, pk=pk)
    return render(request, 'filiacion/atleta_detail.html', {'atleta': atleta})


@login_required
def atleta_create(request):
    if request.method == 'POST':
        form = AtletaForm(request.POST, request.FILES)
        if form.is_valid():
            atleta = form.save()
            return redirect('atleta_detail', pk=atleta.pk)
    else:
        form = AtletaForm()
    return render(request, 'filiacion/atleta_form.html', {'form': form, 'titulo': 'Nuevo Atleta'})


@login_required
def atleta_update(request, pk):
    atleta = get_object_or_404(Atleta, pk=pk)
    if request.method == 'POST':
        form = AtletaForm(request.POST, request.FILES, instance=atleta)
        if form.is_valid():
            form.save()
            return redirect('atleta_detail', pk=atleta.pk)
    else:
        form = AtletaForm(instance=atleta)
    return render(request, 'filiacion/atleta_form.html', {'form': form, 'titulo': f'Editar {atleta.nombres}'})


@login_required
def atleta_delete(request, pk):
    atleta = get_object_or_404(Atleta, pk=pk)
    if request.method == 'POST':
        atleta.delete()
        return redirect('atleta_list')
    return render(request, 'filiacion/atleta_confirm_delete.html', {'atleta': atleta})

# --- Representantes ---


@login_required
def representante_list(request):
    representantes = Representante.objects.all().order_by('apellidos')
    return render(request, 'filiacion/representante_list.html', {'representantes': representantes})


@login_required
def representante_create(request):
    if request.method == 'POST':
        form = RepresentanteForm(request.POST)
        if form.is_valid():
            representante = form.save()
            return redirect('representante_detail', pk=representante.pk)
    else:
        form = RepresentanteForm()
    return render(request, 'filiacion/representante_form.html', {'form': form, 'titulo': 'Nuevo Representante'})


@login_required
def representante_detail(request, pk):
    representante = get_object_or_404(Representante, pk=pk)
    return render(request, 'filiacion/representante_detail.html', {'representante': representante})


@login_required
def representante_update(request, pk):
    representante = get_object_or_404(Representante, pk=pk)
    if request.method == 'POST':
        form = RepresentanteForm(request.POST, instance=representante)
        if form.is_valid():
            form.save()
            return redirect('representante_detail', pk=representante.pk)
    else:
        form = RepresentanteForm(instance=representante)
    return render(request, 'filiacion/representante_form.html', {'form': form, 'titulo': f'Editar {representante.nombres}'})

# Vista para descargar ficha técnica en PDF
@method_decorator(login_required, name='dispatch')
class DescargarFichaPDF(View):
    """
    Vista para generar y descargar la ficha técnica de un atleta en PDF.
    Permite especificar evaluaciones específicas mediante parámetros GET.
    """
    def get(self, request, pk):
        # Obtener parámetros opcionales de evaluaciones
        eval_tecnica_id = request.GET.get('eval_tecnica_id')
        eval_psicosocial_id = request.GET.get('eval_psicosocial_id')
        
        # Convertir a int si existen
        if eval_tecnica_id:
            eval_tecnica_id = int(eval_tecnica_id)
        if eval_psicosocial_id:
            eval_psicosocial_id = int(eval_psicosocial_id)
        
        # Generar el PDF
        pdf_bytes = generar_ficha_tecnica_pdf(pk, eval_tecnica_id, eval_psicosocial_id)
        
        # Obtener el nombre del atleta para el archivo
        atleta = get_object_or_404(Atleta, pk=pk)
        filename = f"ficha_tecnica_{atleta.nombres}_{atleta.apellidos}.pdf"
        
        # Crear respuesta HTTP con el PDF
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
