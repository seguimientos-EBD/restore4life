from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from accounts.forms import EmailForm
from accounts.models import LoginToken

User = get_user_model()


class RequestTokenView(View):
    template_name = 'registration/login.html'
    mode = 'login'

    def get(self, request):
        return render(request, self.template_name, self._context(EmailForm()))

    def post(self, request):
        form = EmailForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._context(form))

        email = form.cleaned_data['email'].lower()
        user, created = User.objects.get_or_create(email=email)
        if created:
            user.set_unusable_password()
            user.save(update_fields=['password'])

        token = LoginToken.objects.create(user=user)
        token_url = request.build_absolute_uri(reverse('token-login', args=[token.token]))
        send_mail(
            subject='Your Restore4Life sign-in link',
            message=render_to_string('accounts/email/token_email.txt', {
                'token_url': token_url,
                'minutes': settings.LOGIN_TOKEN_LIFETIME_MINUTES,
            }),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
        return render(request, 'registration/token_sent.html', {'email': email})

    def _context(self, form):
        return {'form': form, 'is_register': self.mode == 'register'}


class TokenLoginView(View):
    def get(self, request, token):
        login_token = LoginToken.objects.filter(token=token).select_related('user').first()
        if not login_token or not login_token.is_valid():
            messages.error(request, 'That sign-in link is invalid or has expired. Request a new one.')
            return redirect('login')

        login_token.mark_used()
        login(request, login_token.user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'You are now signed in.')
        return redirect(settings.LOGIN_REDIRECT_URL)