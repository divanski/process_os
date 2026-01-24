from django.apps import AppConfig


class {AppConfigName}(AppConfig):
    default_auto_field = 'django.db.BigAutoField'
    name = '{AppName}'
    verbose_name = '{AppVerboseName}'

    def ready(self):
        # Register signal handlers or perform initialization
        pass
