from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Профиль пользователя.
    owner = None  →  сам является владельцем (суперпользователь-арендатор)
    owner = <User>  →  сотрудник, принадлежащий этому владельцу
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='team_members',
        verbose_name='Владелец компании',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль: {self.user.username}'

    def get_tenant_owner(self):
        """Возвращает владельца тенанта (суперпользователя компании)"""
        return self.owner if self.owner_id else self.user
