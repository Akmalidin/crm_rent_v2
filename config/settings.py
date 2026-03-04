import os
from pathlib import Path
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-c94unzxpo+#2z03q_43r0q_5013)xl9&4x0!y(d5sznd1ds#&t'
)

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

_hosts = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = _hosts.split(',') if _hosts else ['*']


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'turbo_response',
    'apps.clients',
    'apps.rental',
    'apps.inventory',
    'apps.main',
    'apps.company',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # статика в продакшне
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.main.middleware.CompanySetupMiddleware',
    'apps.main.middleware.TurboMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # ← ДОБАВЬ ЭТУ СТРОКУ
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.main.context_processors.company_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database — PostgreSQL в продакшне, SQLite локально
_db_url = os.environ.get('DATABASE_URL')
if _db_url:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.parse(_db_url, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'ru'

TIME_ZONE = 'Asia/Bishkek'

USE_I18N = True

USE_TZ = True


# Login/Logout URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Язык
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Bishkek'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8276509481:AAGhKOhn45P8l5belorDsEqqetqGNgHoG3s')
TELEGRAM_ADMIN_CHAT_ID = os.environ.get('TELEGRAM_ADMIN_CHAT_ID', '1289894304')

# ============================================
# JAZZMIN ADMIN НАСТРОЙКИ
# ============================================

JAZZMIN_SETTINGS = {
    "site_title": "CRM Аренда",
    "site_header": "Управление арендой",
    "site_brand": "CRM Аренда",
    "site_logo": None,
    "welcome_sign": "Добро пожаловать в панель управления",
    "copyright": "CRM Аренда Инструментов",

    # Иконки для моделей
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "clients.Client": "fas fa-address-book",
        "rental.RentalOrder": "fas fa-clipboard-list",
        "rental.Payment": "fas fa-money-bill-wave",
        "rental.ReturnDocument": "fas fa-undo",
        "inventory.Product": "fas fa-box",
        "inventory.Category": "fas fa-tags",
        "inventory.Warehouse": "fas fa-warehouse",
        "company.Company": "fas fa-building",
        "main.UserProfile": "fas fa-id-card",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    # Топ-меню
    "topmenu_links": [
        {"name": "На сайт", "url": "/", "new_window": False, "icon": "fas fa-home"},
        {"name": "Клиенты", "url": "/clients/", "icon": "fas fa-users"},
        {"name": "Заказы", "url": "/rental/orders/", "icon": "fas fa-clipboard-list"},
    ],

    # Боковое меню
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    # UI настройки
    "related_modal_active": True,
    "custom_css": None,
    "custom_js": None,
    "use_google_fonts_cdn": False,
    "show_ui_builder": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}