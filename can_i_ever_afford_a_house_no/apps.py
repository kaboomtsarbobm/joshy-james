from django.apps import AppConfig


class PolosConfig(AppConfig):
    # The import package and Django app label are intentionally distinct.
    name = "can_i_ever_afford_a_house_no"
    label = "polo"
    verbose_name = "Polos"
    default_auto_field = "django.db.models.BigAutoField"
    dpy_package = "can_i_ever_afford_a_house_no.polos"
