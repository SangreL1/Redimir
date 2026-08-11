"""
APPS CONFIG — calculadora
"""
from django.apps import AppConfig


class CalculadoraConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.calculadora'
    verbose_name = 'Calculadora Eco-Equivalencia'
