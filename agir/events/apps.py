from django.apps import AppConfig

from ..payments.types import register_payment_type


class EventsConfig(AppConfig):
    name = "agir.events"

    PAYMENT_TYPE = "evenement"

    def ready(self):
        from .views import EventPaidView, notification_listener
        from .actions.rsvps import payment_description_context_generator

        register_payment_type(
            self.PAYMENT_TYPE,
            "Événement payant",
            EventPaidView.as_view(),
            status_listener=notification_listener,
            description_template="events/payment_description.html",
            description_context_generator=payment_description_context_generator,
        )
