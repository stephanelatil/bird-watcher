"""
Django settings for bird_watcher_proj project.

Generated by 'django-admin startproject' using Django 5.0.3.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""

from pathlib import Path
from decouple import Config, RepositoryEnv
from zoneinfo import ZoneInfo

__all__ = ['env']

env_path_dir = Path.cwd()
#not top directory and env does not exist
while env_path_dir != env_path_dir.parent and not env_path_dir.joinpath('.env').exists():
    env_path_dir = env_path_dir.parent #look up one dir
if env_path_dir == env_path_dir.parent:
    print("Unable to find .env file!")
    exit(1)

env = Config(RepositoryEnv(str(env_path_dir.joinpath('.env').absolute())))

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_ROOT = "assets"
VIDEOS_DIRECTORY = "videos"
THUMBNAIL_DIRECTORY = "thumbnails"

PROJECT_NAME = 'birdwatcher'

WEBAPP_HOST = env('WEBAPP_HOST', default='127.0.0.1', cast=str)
WEBAPP_PORT = env('WEBAPP_PORT', default=8000, cast=int)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('DJANGO_SECRET_KEY', cast=str)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['127.0.0.1', WEBAPP_HOST]
CSRF_TRUSTED_ORIGINS = ['http://127.0.0.8:8000', 'http://127.0.0.8', f'http://{WEBAPP_HOST}:{WEBAPP_PORT}', f'http://{WEBAPP_HOST}']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_bootstrap5',
    'constance',
    'birdwatcher'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bird_watcher_proj.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bird_watcher_proj.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

CONSTANCE_BACKEND = 'constance.backends.database.DatabaseBackend'

LOCK_FILE = 'birdwatcher.lock'

# Constance

CONSTANCE_IGNORE_ADMIN_VERSION_CHECK = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING_LEVEL = env('LOGGING_LEVEL', default='WARNING', cast=str)

STREAM_VID_DEVICE = env('STREAM_VID_DEVICE', default='', cast=str)
try:
    with open('/etc/timezone', 'r') as f:
        LOCAL_TIMEZONE = ZoneInfo(f.read())
except:
    LOCAL_TIMEZONE = ZoneInfo('UTC')

VID_OUTPUT_PXL_FORMAT = env("VID_OUTPUT_PXL_FORMAT", default="yuvj444p", cast=str)
VID_CAMERA_DEVICE = env("VID_CAMERA_DEVICE", cast=str)
VID_RESOLUTION = env("VID_RESOLUTION",default="640x400",cast=str)
VID_INPUT_FORMAT = 'yuyv422' #only format supported by v4l2 loopback
VID_FORCED_FRAMERATE = env("VID_FORCED_FRAMERATE", default=-1, cast=float)

MOTION_CHECKS_PER_SECOND = env("MOTION_CHECKS_PER_SECOND", default=2, cast=float)
MOTION_DETECTION_THRESHOLD = env("MOTION_DETECTION_THRESHOLD", default=0.07, cast=float)
RECORD_SECONDS_BEFORE_MOVEMENT = env("RECORD_SECONDS_BEFORE_MOVEMENT", default=2, cast=float)
RECORD_SECONDS_AFTER_MOVEMENT = env("RECORD_SECONDS_AFTER_MOVEMENT", default=2, cast=float)

CONSTANCE_CONFIG = {
    "VID_OUTPUT_PXL_FORMAT" : (VID_OUTPUT_PXL_FORMAT, "", str),
    "VID_RESOLUTION" : (VID_RESOLUTION, "", str),
    "VID_FORCED_FRAMERATE" : (VID_FORCED_FRAMERATE, "", float),

    "MOTION_CHECKS_PER_SECOND" : (MOTION_CHECKS_PER_SECOND, "", float),
    "MOTION_DETECTION_THRESHOLD" : (MOTION_DETECTION_THRESHOLD, "", float),
    "RECORD_SECONDS_BEFORE_MOVEMENT" : (RECORD_SECONDS_BEFORE_MOVEMENT, "", float),
    "RECORD_SECONDS_AFTER_MOVEMENT" : (RECORD_SECONDS_AFTER_MOVEMENT, "", float),
    
    "MOTION_DETECT_AREA_TL_X" : (0.0, "X coordinate of the top left corner of the area to monitor for movement", float),
    "MOTION_DETECT_AREA_TL_Y" : (0.0, "Y coordinate of the top left corner of the area to monitor for movement", float),
    "MOTION_DETECT_AREA_BR_X" : (100.0, "X coordinate of the bottom right corner of the area to monitor for movement", float),
    "MOTION_DETECT_AREA_BR_Y" : (100.0, "Y coordinate of the bottom right corner of the area to monitor for movement", float),
}
