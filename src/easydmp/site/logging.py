DEFAULT = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'select_filter': {
            '()': 'easydmp.lib.log.SQLFilter',
            'keywords': ['SELECT'],
        },
    },
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'mail_admins'],
            'level': 'INFO',
        },
        'easydmp': {
            'handlers': ['console',],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'filters': ['select_filter'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
