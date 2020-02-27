from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    pass

    @property
    def has_superpowers(self):
        return self.is_superuser and self.is_staff and self.is_active
