from django.urls import path
from .views import CalculadoraEcoView, FactoresListView, FactorCreateView, FactorUpdateView

urlpatterns = [
    path('calculadora/eco/',              CalculadoraEcoView.as_view(),  name='calculadora-eco'),
    path('calculadora/factores/',         FactoresListView.as_view(),    name='factores-lista'),
    path('calculadora/factores/nuevo/',   FactorCreateView.as_view(),    name='factor-crear'),
    path('calculadora/factores/<int:pk>/editar/', FactorUpdateView.as_view(), name='factor-editar'),
]
