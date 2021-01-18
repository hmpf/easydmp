from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager


class UserQuerySet(models.QuerySet):

    def have_superpowers(self):
        return self.filter(is_superuser=True, is_active=True, is_staff=True)


class UserManager(BaseUserManager):

    def get_queryset(self):
        return UserQuerySet(self.model, using=self._db)

    def have_superpowers(self):
        return self.get_queryset().have_superpowers()


class User(AbstractUser):
    full_name = models.CharField(max_length=200, blank=True, default='')

    objects = UserManager()

    def __str__(self):
        if self.full_name:
            return '{} ({})'.format(self.full_name, self.get_username())
        return self.get_username()

    @property
    def has_superpowers(self):
        return self.is_superuser and self.is_active and self.is_staff

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name
