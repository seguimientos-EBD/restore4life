from django import forms
from django.utils.html import format_html


class ConnectForm(forms.Form):
    ee_project = forms.CharField(
        label='ID de proyecto de Google Cloud',
        help_text=format_html(
            'Un proyecto propio con la Earth Engine API habilitada '
            '(<a href="https://code.earthengine.google.com/register" target="_blank" rel="noopener">'
            'code.earthengine.google.com/register</a>).',
        ),
    )


class AuthorizeForm(forms.Form):
    auth_code = forms.CharField(label='Código de autorización')