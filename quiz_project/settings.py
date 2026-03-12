import os
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path(__file__).resolve().parent.parent

ENV = dotenv_values(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = ENV.get('SECRET_KEY')
DEBUG = ENV.get('DEBUG') == '1'
ALLOWED_HOSTS = ENV.get('ALLOWED_HOSTS', '').split(',')
CSRF_TRUSTED_ORIGINS = ENV.get('CSRF_TRUSTED_ORIGINS', '').split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'quiz',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'quiz_project.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

ASGI_APPLICATION = 'quiz_project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': ENV.get('DB_NAME'),
        'USER': ENV.get('DB_USER'),
        'PASSWORD': ENV.get('DB_PASSWORD'),
        'HOST': ENV.get('DB_HOST'),
        'PORT': ENV.get('DB_PORT'),
    }
}

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

LOGIN_URL = '/login/'
SESSION_COOKIE_AGE = 86400 * 7
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'uz'
TIME_ZONE = 'Asia/Tashkent'
USE_TZ = True
