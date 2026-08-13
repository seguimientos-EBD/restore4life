from django.conf import settings
from django.db import models

from earthengine.crypto import decrypt, encrypt


class EarthEngineAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earthengine_account')
    ee_project = models.CharField(max_length=255, verbose_name='GCP project')
    refresh_token_encrypted = models.TextField()
    # Earth Engine's 'notebook' flow issues an ephemeral OAuth client per session, so it
    # has to be stored alongside the token: refreshing with ee's static CLIENT_ID fails
    # with 'unauthorized_client'.
    client_id = models.CharField(max_length=255, blank=True, verbose_name='OAuth client')
    client_secret_encrypted = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Earth Engine account'
        verbose_name_plural = 'Earth Engine accounts'

    def __str__(self):
        return f'{self.user} ({self.ee_project})'

    @property
    def refresh_token(self):
        return decrypt(self.refresh_token_encrypted)

    @refresh_token.setter
    def refresh_token(self, value):
        self.refresh_token_encrypted = encrypt(value)

    @property
    def client_secret(self):
        return decrypt(self.client_secret_encrypted) if self.client_secret_encrypted else ''

    @client_secret.setter
    def client_secret(self, value):
        self.client_secret_encrypted = encrypt(value) if value else ''