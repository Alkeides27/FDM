

from django.template.loader import render_to_string
from django.db.models import Sum, Count
from django.conf import settings
from .models import Atleta
from deportivo.models import EvaluacionTecnica, EvaluacionPsicosocial


def generar_ficha_tecnica_pdf(atleta_id, eval_tecnica_id=None, eval_psicosocial_id=None):
    """
    Genera un PDF con la ficha técnica completa de un atleta.
    
    Args:
        atleta_id: ID del atleta
        eval_tecnica_id: ID de la evaluación técnica a incluir (opcional, no usado actualmente)
        eval_psicosocial_id: ID de la evaluación psicosocial a incluir (opcional, no usado actualmente)
    
    Returns:
        bytes: Contenido del PDF generado
    """
    # Obtener el atleta
    atleta = Atleta.objects.get(pk=atleta_id)
    
    # Obtener TODAS las evaluaciones técnicas del atleta (ordenadas por fecha)
    evaluaciones_tecnicas = atleta.evaluaciones_tecnicas.all().order_by('-fecha_evaluacion')
    
    # Obtener TODAS las evaluaciones psicosociales del atleta (ordenadas por fecha)
    evaluaciones_psicosociales = atleta.evaluaciones_psicosociales.all().order_by('-fecha_evaluacion')
    
    # Calcular estadísticas agregadas expandidas
    from django.db.models import Avg
    estadisticas = atleta.estadisticas.aggregate(
        total_goles=Sum('goles'),
        total_partidos=Count('partido', distinct=True),
        total_asistencias=Sum('asistencias'),
        total_tarjetas_amarillas=Sum('tarjetas_amarillas'),
        total_tarjetas_rojas=Sum('tarjetas_rojas'),
        calificacion_promedio=Avg('calificacion_dt')
    )
    
    # Preparar contexto para el template
    contexto = {
        'atleta': atleta,
        'evaluaciones_tecnicas': evaluaciones_tecnicas,
        'evaluaciones_psicosociales': evaluaciones_psicosociales,
        'estadisticas': estadisticas,
        'MEDIA_ROOT': settings.MEDIA_ROOT,
    }
    
    # Agregar URL de foto compatible con Windows y Linux
    if atleta.foto_perfil:
        from pathlib import Path
        from urllib.request import pathname2url
        foto_path = Path(atleta.foto_perfil.path)
        # Convertir ruta absoluta a URL file:// compatible con ambos OS
        foto_url = 'file:' + pathname2url(str(foto_path))
        contexto['foto_url'] = foto_url
    
    # Renderizar el HTML
    html_string = render_to_string('filiacion/reports/ficha_tecnica_pdf.html', contexto)
    
    # Generar el PDF
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as e:
        raise ImportError(
            "WeasyPrint no está disponible o carece de las bibliotecas del sistema necesarias (como Cairo/Pango)."
        ) from e
    
    pdf_bytes = HTML(string=html_string).write_pdf()
    
    return pdf_bytes
