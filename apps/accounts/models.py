from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user so profile fields can be added later without a painful migration."""

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def __str__(self):
        return self.get_full_name() or self.username
