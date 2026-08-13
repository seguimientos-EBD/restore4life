from django import forms
from django.utils.html import format_html


class ConnectForm(forms.Form):
    ee_project = forms.CharField(
        label='Google Cloud project ID',
        help_text=format_html(
            'A project of your own with the Earth Engine API enabled '
            '(<a href="https://code.earthengine.google.com/register" target="_blank" rel="noopener">'
            'code.earthengine.google.com/register</a>).',
        ),
    )


class AuthorizeForm(forms.Form):
    auth_code = forms.CharField(label='Authorization code')