import os
import sys
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Fichero .env
SECRET_KEY = config('SECRET_KEY')
DJANGO_CONFIGURATION = config('DJANGO_CONFIGURATION')
DEBUG = config('DEBUG', default=False, cast=bool)
STATIC_ROOT = config('STATIC_ROOT', default=None)
MEDIA_ROOT = config('MEDIA_ROOT')
ON_PROD = True if config('DJANGO_CONFIGURATION') == 'Prod' else False
CREATE_DEFAULT_ADMIN = config('CREATE_DEFAULT_ADMIN', default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost,http://127.0.0.1", cast=Csv())
EE_TOKEN_ENCRYPTION_KEY = config('EE_TOKEN_ENCRYPTION_KEY')

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# Passwordless (magic-link) authentication
LOGIN_TOKEN_LIFETIME_MINUTES = config('LOGIN_TOKEN_LIFETIME_MINUTES', default=30, cast=int)
LOGIN_TOKEN_LIFETIME = timedelta(minutes=LOGIN_TOKEN_LIFETIME_MINUTES)

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    # Custom apps
    'accounts',
    'generic',
    'areas',
    'earthengine',
    'hydroperiod',
    # 3rd party apps
    'django_extensions',
    'django_yarnpkg',
    'sass_processor',
    'django_bootstrap5',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'generic.middleware.LoginRequiredMiddleware',
]

ROOT_URLCONF = 'restore4life.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'generic.context_processors.earthengine_account',
            ],
        },
    },
]

WSGI_APPLICATION = 'restore4life.wsgi.application'


STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'sass_processor.finders.CssFinder',
    'django_yarnpkg.finders.NodeModulesFinder',
]

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

NODE_MODULES_ROOT = os.path.join(BASE_DIR, 'node_modules')
SASS_PROCESSOR_INCLUDE_DIRS = [
    os.path.join(BASE_DIR, 'node_modules'),
    os.path.join(BASE_DIR, 'static'),
]

YARN_INSTALLED_APPS = (
    "@popperjs/core@^2.11.8",
    'bootstrap@^5.3.8',
    "bootstrap-icons@^1.11.3",
    "jquery@^4.0.0",
    "jquery-ui@^1.14.2",
    "leaflet@^1.9.4",
    "leaflet.fullscreen@^3.0.1",
    # Same drawing plugin ipyleaflet uses under the hood, so drawing an ROI here
    # behaves as it does in the notebook widget this app was ported from.
    "leaflet-draw@^1.0.4",
)

# Column split for horizontal forms. Only the fields that ask for layout="horizontal"
# use it, and the only ones that do (the hydroperiod panel) are small-sized: hence the
# col-form-label-sm.
BOOTSTRAP5 = {
    'horizontal_label_class': 'col-5 col-form-label-sm',
    'horizontal_field_class': 'col-7',
}


DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST': 'localhost',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
MEDIA_URL = '/media/'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
if ON_PROD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='no-reply@restore4life.local')
    EMAIL_HOST = config('EMAIL_HOST', default='')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_PRELOAD = True
    import sentry_sdk
    sentry_sdk.init(
        dsn=config('SENTRY_URL'),
        environment=config('SENTRY_ENVIRONMENT'),
        sample_rate=1.0,
        # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring.
        traces_sample_rate=0.0,
        # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=0.0,
    )
