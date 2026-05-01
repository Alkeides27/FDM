from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()  # carga variables desde .env en BASE_DIR

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-clave-temporal')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG') == 'True'

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # App para funcionalidades transversales
    'core.apps.CoreConfig',

    # Apps de negocio
    'administracion.apps.AdministracionConfig',
    'filiacion.apps.FiliacionConfig',
    'deportivo.apps.DeportivoConfig',
    'finanzas.apps.FinanzasConfig',

    # Autenticación
    'accounts.apps.AccountsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.RatelimitLoggingMiddleware',
]

ROOT_URLCONF = 'project_gestion.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'project_gestion.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'es-ve'

TIME_ZONE = 'America/Caracas'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ──────────────────────────────────────────────────────────────
# AUTH SYSTEM
# ──────────────────────────────────────────────────────────────
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Sesión
SESSION_COOKIE_AGE = 60 * 60 * 8      # 8 horas
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# ──────────────────────────────────────────────────────────────
# RATE LIMITING (django-ratelimit)
# ──────────────────────────────────────────────────────────────
RATELIMIT_ENABLE = True

# Cache backend: locmem en dev, Redis en prod (toggle por env)
USE_REDIS = os.getenv('USE_REDIS', 'False') == 'True'

if USE_REDIS:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ingenium-fdm-cache',
        }
    }

# IP detection (ajustar segun deployment)
# - Desarrollo local: comentar las siguientes lineas
# - Detras de Nginx: 'HTTP_X_REAL_IP'
# - Detras de Cloudflare: 'HTTP_CF_CONNECTING_IP'
# - Detras de proxy generico: 'HTTP_X_FORWARDED_FOR'
# RATELIMIT_IP_META_KEY = 'HTTP_X_REAL_IP'

# ──────────────────────────────────────────────────────────────
# STATIC FILES
# ──────────────────────────────────────────────────────────────
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
]

# ──────────────────────────────────────────────────────────────
# LOGGING (Security & Finanzas Bot Integrados)
# ──────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {

        'security_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'security',
        },

        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {

        'security.ratelimit': {
            'handlers': ['security_file'],
            'level': 'INFO',
            'propagate': False,
        },

        'finanzas.telegram_bot': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
