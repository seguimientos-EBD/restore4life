from accounts import views as accounts_views
from django.contrib.auth import views as auth_views
from django.urls import path

from generic.views import CitationView, FaqView, IndexView

urlpatterns = [
    path('login/', accounts_views.RequestTokenView.as_view(), name="login"),
    path('logout/', auth_views.LogoutView.as_view(), name="logout"),
    path(
        'register/',
        accounts_views.RequestTokenView.as_view(template_name='registration/register.html', mode='register'),
        name="register",
    ),
    path('token/<str:token>/', accounts_views.TokenLoginView.as_view(), name="token-login"),
    path('', IndexView.as_view(), name='index'),
    path('citation/', CitationView.as_view(), name='citation'),
    path('faq/', FaqView.as_view(), name='faq'),
]
