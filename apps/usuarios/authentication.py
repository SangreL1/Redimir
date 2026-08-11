from django.contrib.auth.backends import ModelBackend
from apps.usuarios.models import Usuario


class RutBackend(ModelBackend):
    """Backend de autenticación que acepta RUT como username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None
        rut = username.strip().upper()
        try:
            user = Usuario.objects.get(rut=rut)
        except Usuario.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return Usuario.objects.get(pk=user_id)
        except Usuario.DoesNotExist:
            return None
