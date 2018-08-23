from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import UpdateView, DetailView, RedirectView

from agir.authentication.view_mixins import HardLoginRequiredMixin
from agir.payments.actions import redirect_to_payment, create_payment
from agir.payments.models import Payment
from agir.payments.payment_modes import PAYMENT_MODES
from agir.people.models import PersonFormSubmission
from agir.people.actions.person_forms import get_people_form_class, get_formatted_submission

from ..actions.rsvps import (
    rsvp_to_free_event, rsvp_to_paid_event_and_create_payment, validate_payment_for_rsvp, set_guest_number,
    add_free_identified_guest, add_paid_identified_guest_and_get_payment, validate_payment_for_guest, is_participant,
    cancel_payment_for_guest, cancel_payment_for_rsvp, RSVPException
)
from ..models import Event, RSVP
from ..tasks import send_rsvp_notification
from ..forms import BillingForm, GuestsForm, BaseRSVPForm


class RSVPEventView(HardLoginRequiredMixin, DetailView):
    """RSVP to an event, check one's RSVP, or add guests to your RSVP

    """
    model = Event
    template_name = 'events/rsvp_event.html'
    default_error_message = _(
        "Il y a eu un problème avec votre inscription. Merci de bien vouloir vérifier si vous n'êtes "
        "pas déjà inscrit⋅e, et retenter si nécessaire."
    )
    context_object_name = 'event'

    def get_form(self):
        if self.event.subscription_form is None:
            return None

        form_class = get_people_form_class(self.event.subscription_form, BaseRSVPForm)

        kwargs = {
            'instance': None if self.user_is_already_rsvped else self.request.user.person,
            'is_guest': self.user_is_already_rsvped,
        }

        if self.request.method in ('POST', 'PUT'):
            kwargs['data'] = self.request.POST

        return form_class(**kwargs)

    def get_context_data(self, **kwargs):
        rsvp = None
        if self.request.user.is_authenticated:
            try:
                rsvp = RSVP.objects.get(event=self.event, person=self.request.user.person)
            except RSVP.DoesNotExist:
                pass

        form = self.get_form()

        return super().get_context_data(
            form=form,
            event=self.event,
            rsvp=rsvp,
            submission_data=get_formatted_submission(rsvp.form_submission) if rsvp and rsvp.form_submission else None,
            guests_submission_data=[
                (guest.get_status_display(), get_formatted_submission(guest.submission) if guest.submission else [])
                for guest in rsvp.identified_guests.select_related('submission')
            ] if rsvp else None,
            **kwargs
        )

    def get(self, request, *args, **kwargs):
        self.event = self.object = self.get_object()
        if self.event.subscription_form is None:
            return HttpResponseRedirect(reverse('view_event', args=[self.event.pk]))

        context = self.get_context_data(object=self.event)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.event = self.object = self.get_object()

        if self.user_is_already_rsvped:
            return self.handle_adding_guests()
        else:
            return self.handle_rsvp()

    def handle_rsvp(self):
        try:
            if not self.event.subscription_form:
                # Without any subscription form, we either simply create the rsvp, or redirect to payment
                if self.event.is_free:
                    # we create the RSVP here for free events
                    rsvp_to_free_event(self.event, self.request.user.person)
                    return self.redirect_to_event(
                        message=_("Merci de nous avoir signalé votre participation à cet événement."),
                        level=messages.SUCCESS
                    )
                else:
                    return self.redirect_to_billing_form()

            form = self.get_form()

            if not form.is_valid():
                context = self.get_context_data(object=self.event)
                return self.render_to_response(context)

            if form.cleaned_data['is_guest']:
                self.redirect_to_event(message=self.default_error_message)

            if self.event.is_free:
                with transaction.atomic():
                    form.save()
                    rsvp_to_free_event(self.event, self.request.user.person, form_submission=form.submission)
                    return self.redirect_to_event(
                        message=_("Merci de nous avoir signalé votre participation à cet événenement."),
                        level=messages.SUCCESS
                    )

            else:
                form.save()
                return self.redirect_to_billing_form(form.submission)
        except RSVPException as e:
            return self.redirect_to_event(message=str(e))

    def handle_adding_guests(self):
        try:
            if not self.event.subscription_form and self.event.is_free:
                guests_form = GuestsForm(self.request.POST)
                if not guests_form.is_valid():
                    return self.redirect_to_event(message=self.default_error_message)

                guests = guests_form.cleaned_data['guests']

                set_guest_number(self.event, self.request.user.person, guests)
                return self.redirect_to_event(
                    message=_("Merci, votre nombre d'invités a été mis à jour !"),
                    level=messages.SUCCESS
                )

            if not self.event.subscription_form:
                return self.redirect_to_billing_form(is_guest=True)

            form = self.get_form()

            if not form.is_valid():
                context = self.get_context_data(object=self.event)
                return self.render_to_response(context)

            if not form.cleaned_data['is_guest']:
                return self.redirect_to_event(message=self.default_error_message)

            if self.event.is_free:
                with transaction.atomic():
                    # do not save the person, only the submission
                    form.save_submission(self.request.user.person)
                    add_free_identified_guest(self.event, self.request.user.person, form.submission)
                return self.redirect_to_event(
                    message=_("Merci, votre invité a bien été enregistré !"),
                    level=messages.SUCCESS
                )
            else:
                form.save_submission(self.request.user.person)
                return self.redirect_to_billing_form(form.submission, is_guest=True)
        except RSVPException as e:
            return self.redirect_to_event(message=str(e))

    def redirect_to_event(self, *, message, level=messages.ERROR):
        if message is not None:
            messages.add_message(
                request=self.request,
                level=level,
                message=message
            )

        return HttpResponseRedirect(reverse('view_event', args=[self.event.pk]))

    def redirect_to_billing_form(self, submission=None, is_guest=False, is_manager_ticket=False):
        if submission:
            self.request.session['rsvp_submission'] = submission.pk
        elif 'rsvp_submission' in self.request.session:
            del self.request.session['rsvp_submission']
        self.request.session['rsvp_event'] = str(self.event.pk)
        self.request.session['is_guest'] = is_guest
        self.request.session['is_manager_ticket'] = is_manager_ticket

        return HttpResponseRedirect(reverse('pay_event'))

    @cached_property
    def user_is_already_rsvped(self):
        return is_participant(self.event, self.request.user.person)


class ChangeRSVPPaymentView(HardLoginRequiredMixin, DetailView):
    def get_queryset(self):
        return self.request.user.person.rsvps\
            .exclude(payment=None)\
            .exclude(payment__status=Payment.STATUS_COMPLETED)\
            .filter(
                payment__mode__in=[mode.id for mode in PAYMENT_MODES.values() if mode.can_cancel]
            )

    def get(self, *args, **kwargs):
        rsvp = self.get_object()
        if rsvp.form_submission:
            self.request.session['rsvp_submission'] = rsvp.form_submission.pk
        elif 'rsvp_submission' in self.request.session:
            del self.request.session['rsvp_submission']
        self.request.session['rsvp_event'] = str(rsvp.event.pk)
        self.request.session['is_guest'] = False

        return HttpResponseRedirect(reverse('pay_event'))


class PayEventView(HardLoginRequiredMixin, UpdateView):
    """View for the billing form for paid events

    """
    form_class = BillingForm
    template_name = 'events/pay_event.html'
    generic_error_message = _(
        "Il y a eu un problème avec votre paiement. Merci de réessayer plus tard"
    )

    def get_object(self, queryset=None):
        return self.request.user.person

    def get_context_data(self, **kwargs):
        if self.submission:
            # this form is instantiated only to get the labels for every field
            form = get_people_form_class(self.submission.form)(self.request.user.person)
        kwargs.update({
            'event': self.event,
            'submission': self.submission,
            'price': self.event.get_price(self.submission) / 100,
            'submission_data': get_formatted_submission(self.submission) if self.submission else None
        })
        return super().get_context_data(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        submission_pk = self.request.session.get('rsvp_submission')
        event_pk = self.request.session.get('rsvp_event')

        if not event_pk:
            return HttpResponseBadRequest('no event')

        try:
            self.event = Event.objects.upcoming().get(pk=event_pk)
        except Event.DoesNotExist:
            return HttpResponseBadRequest('no event')

        if self.event.subscription_form:
            if not submission_pk:
                return self.display_error_message(self.generic_error_message)

            try:
                self.submission = PersonFormSubmission.objects.get(pk=submission_pk)
            except PersonFormSubmission.DoesNotExist:
                return self.display_error_message(self.generic_error_message)

            if self.submission.form != self.event.subscription_form:
                return self.display_error_message(self.generic_error_message)
        else:
            self.submission = None

        self.is_guest = self.request.session.get('is_guest', False)
        self.is_manager_ticket = self.request.session.get('is_manager_ticket', False)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['submission'] = self.submission
        kwargs['event'] = self.event
        kwargs['is_guest'] = self.is_guest
        kwargs['is_manager_ticket'] = self.is_manager_ticket
        return kwargs

    def form_valid(self, form):
        event = form.cleaned_data['event']
        person = self.request.user.person
        submission = form.cleaned_data['submission']
        is_guest = form.cleaned_data['is_guest']
        is_manager_ticket = form.cleaned_data['is_manager_ticket']
        payment_mode = form.cleaned_data['payment_mode']

        if not is_guest:
            # we save the billing information only if the person is paying for herself or himself
            form.save()

        with transaction.atomic():
            try:
                if is_guest:
                    payment = add_paid_identified_guest_and_get_payment(event, person, payment_mode, submission)
                    if is_manager_ticket and self.request.session['is_manager_ticket']:
                        if payment.get_mode_class().can_admin:
                            messages.add_message(
                                request=self.request,
                                message="La personne a bien été inscrite !",
                            )

                            return HttpResponseRedirect(reverse('ticket_event'), args=[self.event.pk])

                else:
                    payment = rsvp_to_paid_event_and_create_payment(event, person, payment_mode, submission)

            except RSVPException as e:
                return self.display_error_message(str(e))

        return redirect_to_payment(payment)

    def display_error_message(self, message, level=messages.ERROR):
        messages.add_message(
            request=self.request,
            message=message,
            level=level
        )

        return HttpResponseRedirect(reverse('view_event', args=[self.event.pk]))


class EventPaidView(RedirectView):
    """View shown when the event has been paid

    """

    def get_redirect_url(self, *args, **kwargs):
        payment = self.kwargs['payment']
        event = Event.objects.get(pk=self.kwargs['payment'].meta['event_id'])

        messages.add_message(
            request=self.request,
            level=messages.SUCCESS,
            message=f"Votre inscription {payment.get_price_display()} pour l'événement « {event.name} » a bien été enregistré. "
                    f"Votre inscription sera confirmée dès validation du paiement."
        )
        return reverse('view_event', args=[self.kwargs['payment'].meta['event_id']])


def notification_listener(payment):
    submission_pk = payment.meta.get('submission_id')
    event_pk = payment.meta.get('event_id')
    event = Event.objects.get(pk=event_pk)

    if payment.meta.get('VERSION') == '2':
        # VERSION 2
        is_guest = payment.meta['is_guest']

        if payment.status in [Payment.STATUS_REFUSED, Payment.STATUS_CANCELED, Payment.STATUS_ABANDONED]:
            if is_guest:
                cancel_payment_for_guest(payment)
            else:
                cancel_payment_for_rsvp(payment)

        if payment.status == Payment.STATUS_COMPLETED:
            # we don't check for cancellation of the event because we want all actually paid rsvps to be registered in case
            # we need to manage refunding

            # RSVP or IdentifiedGuest model has already been created, only need to confirm it
            if is_guest:
                validate_payment_for_guest(payment)
            else:
                validate_payment_for_rsvp(payment)

    else:
        # VERSION 1
        if payment.status == Payment.STATUS_COMPLETED:
            if event.subscription_form:
                if not submission_pk:
                    return HttpResponseBadRequest('no submission')
                try:
                    submission = PersonFormSubmission.objects.get(pk=submission_pk)
                except PersonFormSubmission.DoesNotExist:
                    return HttpResponseBadRequest('no submission')
            else:
                submission = None

            with transaction.atomic():
                try:
                    rsvp = RSVP.objects.select_for_update().get(person=payment.person, event=event)
                    created = False
                except RSVP.DoesNotExist:
                    rsvp = RSVP.objects.create(
                        person=payment.person,
                        event=event
                    )
                    created = True

                if created:
                    rsvp.form_submission = submission
                    rsvp.payment = payment
                else:
                    rsvp.guests += 1
                    # faking creating a "free" guest
                    guest = add_free_identified_guest(event, payment.person, submission)
                    guest.payment = payment
                    guest.save()

                rsvp.save()
            send_rsvp_notification.delay(rsvp.pk)


class TicketingView(RSVPEventView):
    template_name = 'events/ticketing.html'
    permissions_required = ('events.change_event',)
    error_messages = {
        'denied': _("Vous ne pouvez pas accéder à cette page sans être organisateur de l'événement.")
    }

    def redirect_to_ticketing(self, *, message, level=messages.ERROR):
        if message is not None:
            messages.add_message(
                request=self.request,
                level=level,
                message=message
            )

        return HttpResponseRedirect(reverse('ticket_event', args=[self.event.pk]))

    def post(self):
        self.event = self.get_object()
        try:
            form = self.get_form()

            if not form.is_valid():
                context = self.get_context_data(object=self.event)
                return self.render_to_response(context)

            if not form.cleaned_data['is_guest']:
                return self.redirect_to_ticketing(message=self.default_error_message)

            form.save_submission(self.request.user.person)

            return self.redirect_to_billing_form(form.submission)

        except RSVPException as e:
            return self.redirect_to_ticketing(message=str(e))
