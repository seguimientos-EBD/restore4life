import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from earthengine import oauth
from earthengine.forms import AuthorizeForm, ConnectForm
from earthengine.models import EarthEngineAccount

logger = logging.getLogger(__name__)

SESSION_CODE_VERIFIER = 'ee_code_verifier'
SESSION_EE_PROJECT = 'ee_project_pending'


class ConnectView(LoginRequiredMixin, View):
    template_name = 'earthengine/connect.html'

    def get(self, request):
        account = EarthEngineAccount.objects.filter(user=request.user).first()
        if account:
            return render(request, self.template_name, {'account': account})
        return render(request, self.template_name, {'form': ConnectForm()})

    def post(self, request):
        account = EarthEngineAccount.objects.filter(user=request.user).first()
        if account:
            return render(request, self.template_name, {'account': account})

        form = ConnectForm(request.POST)
        if form.is_valid():
            auth_url, code_verifier = oauth.build_authorization_url()
            request.session[SESSION_CODE_VERIFIER] = code_verifier
            request.session[SESSION_EE_PROJECT] = form.cleaned_data['ee_project']
            return render(request, self.template_name, {
                'auth_url': auth_url,
                'authorize_form': AuthorizeForm(),
            })

        return render(request, self.template_name, {'form': form})


class AuthorizeView(LoginRequiredMixin, View):
    template_name = 'earthengine/connect.html'

    def post(self, request):
        code_verifier = request.session.get(SESSION_CODE_VERIFIER)
        ee_project = request.session.get(SESSION_EE_PROJECT)
        if not code_verifier or not ee_project:
            messages.error(request, 'La conexión con Earth Engine ha caducado, empieza de nuevo.')
            return redirect('earthengine:connect')

        form = AuthorizeForm(request.POST)
        if form.is_valid():
            try:
                refresh_token, client_id, client_secret = oauth.exchange_code(
                    form.cleaned_data['auth_code'], code_verifier,
                )
            except Exception:
                logger.exception('Error canjeando el código de autorización de Earth Engine')
                messages.error(request, 'El código de autorización no es válido o ha caducado.')
            else:
                account, _ = EarthEngineAccount.objects.get_or_create(user=request.user)
                account.ee_project = ee_project
                account.refresh_token = refresh_token
                account.client_id = client_id
                account.client_secret = client_secret
                account.save()
                del request.session[SESSION_CODE_VERIFIER]
                del request.session[SESSION_EE_PROJECT]
                messages.success(request, 'Cuenta de Earth Engine conectada.')
                return redirect('index')

        auth_url, code_verifier = oauth.build_authorization_url()
        request.session[SESSION_CODE_VERIFIER] = code_verifier
        return render(request, self.template_name, {'auth_url': auth_url, 'authorize_form': form})


class DisconnectView(LoginRequiredMixin, View):
    def post(self, request):
        EarthEngineAccount.objects.filter(user=request.user).delete()
        messages.success(request, 'Cuenta de Earth Engine desconectada.')
        return redirect('earthengine:connect')
