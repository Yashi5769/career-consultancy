from django.apps import AppConfig


class CareerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # --- FIX: This name MUST match the full path to your app ---
    name = 'career_consulting.career'

