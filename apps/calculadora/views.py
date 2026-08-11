"""
VISTAS CALCULADORA ECO-EQUIVALENCIA — REDIMIR
Permite calcular y configurar factores de eco-equivalencia.
"""
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone

from .models import FactorEcoEquivalencia


def _es_admin(user):
    return user.rol in ['admin', 'gerencia'] or user.is_staff or user.is_superuser


@method_decorator(login_required, name='dispatch')
class CalculadoraEcoView(View):
    """Calculadora de eco-equivalencia para un período y cliente."""
    template_name = 'calculadora/eco.html'

    def get(self, request):
        from apps.empresas.models import Empresa
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        materiales = FactorEcoEquivalencia.MATERIALES
        return render(request, self.template_name, {
            'empresas': empresas,
            'materiales': materiales,
        })

    def post(self, request):
        """Calcular eco-equivalencia para un set de materiales/pesos."""
        from decimal import Decimal
        from apps.empresas.models import Empresa

        empresa_id = request.POST.get('empresa')
        materiales_kg = {}

        for mat, _ in FactorEcoEquivalencia.MATERIALES:
            val = request.POST.get(f'kg_{mat}', '').strip()
            if val:
                try:
                    materiales_kg[mat] = Decimal(val)
                except Exception:
                    pass

        resultado = {
            'kg_total': Decimal('0'),
            'agua_L': Decimal('0'),
            'co2_kg': Decimal('0'),
            'energia_kwh': Decimal('0'),
            'petroleo_L': Decimal('0'),
            'arboles': Decimal('0'),
            'desglose': [],
        }

        for mat, kg in materiales_kg.items():
            factor = FactorEcoEquivalencia.get_factor_activo(mat)
            if not factor:
                resultado['desglose'].append({'material': mat, 'kg': float(kg),
                                               'agua': 0, 'co2': 0, 'energia': 0, 'petroleo': 0, 'arboles': 0})
                resultado['kg_total'] += kg
                continue

            agua      = kg * Decimal(str(factor.factor_agua_lxkg))
            co2       = kg * Decimal(str(factor.factor_co2_kgxkg))
            energia   = kg * Decimal(str(factor.factor_energia_kwhxkg))
            petroleo  = kg * Decimal(str(factor.factor_petroleo_lxkg))
            arboles   = kg * Decimal(str(factor.factor_arboles_kgxkg))

            resultado['kg_total']    += kg
            resultado['agua_L']      += agua
            resultado['co2_kg']      += co2
            resultado['energia_kwh'] += energia
            resultado['petroleo_L']  += petroleo
            resultado['arboles']     += arboles

            nombre_mat = dict(FactorEcoEquivalencia.MATERIALES).get(mat, mat)
            resultado['desglose'].append({
                'material': nombre_mat, 'kg': float(kg),
                'agua': float(agua), 'co2': float(co2),
                'energia': float(energia), 'petroleo': float(petroleo),
                'arboles': float(arboles),
            })

        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        empresa = None
        if empresa_id:
            try:
                empresa = Empresa.objects.get(pk=empresa_id)
            except Empresa.DoesNotExist:
                pass

        return render(request, self.template_name, {
            'empresas': empresas,
            'empresa': empresa,
            'materiales': FactorEcoEquivalencia.MATERIALES,
            'resultado': resultado,
            'form_data': request.POST,
        })


@method_decorator(login_required, name='dispatch')
class FactoresListView(View):
    template_name = 'calculadora/factores.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'Sin permisos.')
            return redirect('dashboard')
        factores = FactorEcoEquivalencia.objects.all().order_by('material', '-fecha_inicio')
        return render(request, self.template_name, {'factores': factores})


@method_decorator(login_required, name='dispatch')
class FactorCreateView(View):
    template_name = 'calculadora/factor_form.html'

    def get(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')
        return render(request, self.template_name, {
            'materiales': FactorEcoEquivalencia.MATERIALES,
            'factor': None,
        })

    def post(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')

        try:
            factor = FactorEcoEquivalencia.objects.create(
                material=request.POST['material'],
                factor_agua_lxkg=request.POST.get('agua', 0),
                factor_co2_kgxkg=request.POST.get('co2', 0),
                factor_energia_kwhxkg=request.POST.get('energia', 0),
                factor_petroleo_lxkg=request.POST.get('petroleo', 0),
                factor_arboles_kgxkg=request.POST.get('arboles', 0),
                fecha_inicio=request.POST.get('fecha_inicio') or timezone.now().date(),
                notas=request.POST.get('notas', ''),
                activo=True,
                version=1,
                usuario_modificador=request.user,
            )

            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='configuracion',
                modelo='FactorEcoEquivalencia',
                registro_id=factor.id,
                campo='factores',
                valor_anterior='',
                valor_nuevo=f"AGUA:{factor.factor_agua_lxkg}, CO2:{factor.factor_co2_kgxkg}, KWH:{factor.factor_energia_kwhxkg}",
                detalles=f"Creado nuevo factor para material {factor.get_material_display()} (v1)",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, 'Factor creado exitosamente.')
            return redirect('factores-lista')
        except Exception as e:
            messages.error(request, f'Error: {e}')
            return render(request, self.template_name, {
                'materiales': FactorEcoEquivalencia.MATERIALES, 'form_data': request.POST,
            })


@method_decorator(login_required, name='dispatch')
class FactorUpdateView(View):
    template_name = 'calculadora/factor_form.html'

    def get(self, request, pk):
        if not _es_admin(request.user):
            return redirect('dashboard')
        factor = get_object_or_404(FactorEcoEquivalencia, pk=pk)
        return render(request, self.template_name, {
            'factor': factor, 'materiales': FactorEcoEquivalencia.MATERIALES,
        })

    def post(self, request, pk):
        if not _es_admin(request.user):
            return redirect('dashboard')
        factor = get_object_or_404(FactorEcoEquivalencia, pk=pk)
        try:
            val_ant = f"AGUA:{factor.factor_agua_lxkg}, CO2:{factor.factor_co2_kgxkg}, KWH:{factor.factor_energia_kwhxkg}, PETROLEO:{factor.factor_petroleo_lxkg}, ARBOLES:{factor.factor_arboles_kgxkg}"

            factor.factor_agua_lxkg      = request.POST.get('agua', 0)
            factor.factor_co2_kgxkg      = request.POST.get('co2', 0)
            factor.factor_energia_kwhxkg = request.POST.get('energia', 0)
            factor.factor_petroleo_lxkg  = request.POST.get('petroleo', 0)
            factor.factor_arboles_kgxkg  = request.POST.get('arboles', 0)
            factor.notas     = request.POST.get('notas', '')
            factor.activo    = bool(request.POST.get('activo'))
            factor.version  += 1
            factor.usuario_modificador = request.user
            factor.save()

            val_nuev = f"AGUA:{factor.factor_agua_lxkg}, CO2:{factor.factor_co2_kgxkg}, KWH:{factor.factor_energia_kwhxkg}, PETROLEO:{factor.factor_petroleo_lxkg}, ARBOLES:{factor.factor_arboles_kgxkg}"

            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='configuracion',
                modelo='FactorEcoEquivalencia',
                registro_id=factor.id,
                campo='factores_conversion',
                valor_anterior=val_ant,
                valor_nuevo=val_nuev,
                detalles=f"Modificado factor para {factor.get_material_display()} a versión {factor.version}",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, 'Factor actualizado.')
            return redirect('factores-lista')
        except Exception as e:
            messages.error(request, f'Error: {e}')
            return render(request, self.template_name, {'factor': factor, 'materiales': FactorEcoEquivalencia.MATERIALES})

