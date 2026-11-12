from django.contrib.auth.backends import ModelBackend
from apps.usuarios.models import Usuario
from apps.usuarios.utils import variantes_rut


class RutBackend(ModelBackend):
    """Backend de autenticación que acepta RUT en cualquier formato."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None

        # Si parece email, buscar por email directamente
        if '@' in username:
            try:
                user = Usuario.objects.get(email=username.strip().lower())
            except Usuario.DoesNotExist:
                return None
        else:
            # Probar todas las variantes del RUT (con puntos, sin puntos, solo dígitos)
            variantes = variantes_rut(username)
            user = None
            for variante in variantes:
                try:
                    user = Usuario.objects.get(rut=variante)
                    break
                except Usuario.DoesNotExist:
                    continue
            if user is None:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
