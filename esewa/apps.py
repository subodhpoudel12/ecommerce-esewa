"""
your_app Django application initialization.
"""
from django.apps import AppConfig
class EsewaConfig(AppConfig):
    """
    Configuration for the your_app Django application.
    """
    name = 'esewa'
    plugin_app = {
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'esewa',
                'relative_path': 'urls',
            }
        },
        'settings_config': {
            'lms.djangoapp': {
                'common': {'relative_path': 'settings'},
            }
        },
    } 