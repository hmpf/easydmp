from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    full_name = models.CharField(max_length=200, blank=True, default='')

    @property
    def has_superpowers(self):
        return self.is_superuser and self.is_staff and self.is_active

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name
