import logging
import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url

from .processors import esewa

logger = logging.getLogger(__name__)

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')

ESEWA_SUCCESS_CODES = ['100', '111']

class EsewaResponseView(EdxOrderPlacementMixin, View):
    """
    View to handle the response from Esewa after processing the payment.
    """
    @property
    def payment_processor(self):
        return esewa(self.request.site)

    @method_decorator(transaction.non_atomic_requests)
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(EsewaResponseView, self).dispatch(request, *args, **kwargs)

    def _verify_response(self, payment_reference):
        """
        Verify the given payment_reference number to confirm that it is for a valid transaction
        and return the verification response data.
        """
        partner_short_code = self.request.site.siteconfiguration.partner.short_code
        configuration = settings.PAYMENT_PROCESSOR_CONFIG[partner_short_code.lower()][self.payment_processor.NAME]
        api_parameters = {
            "merchant_email": configuration['merchant_email'],
            "secret_key": configuration['secret_key'],
            "payment_reference": payment_reference
        }
        response = requests.post("https://rc-epay.esewa.com.np/api/epay/main/v2/form", data=api_parameters)
        return response.json()

    def _get_basket(self, basket_id):
        """
        Return the basket for the given id or None.
        """
        try:
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
            Applicator().apply(basket, basket.owner, self.request)
            return basket
        except (ValueError, ObjectDoesNotExist):
            return None

    def post(self, request):
        """
        Handle the POST request from Esewa and redirect to the appropriate page based on the status.
        """
        transaction_id = 'Unknown'
        basket = None
        verification_data = {}
        try:
            payment_reference = request.POST.get('payment_reference')
            if not payment_reference:
                logger.error('Received an invalid Esewa merchant notification [%s]', request.POST)
                return redirect(reverse('payment_error'))

            logger.info('Received Esewa merchant notification with payment_reference %s', payment_reference)
            verification_data = self._verify_response(payment_reference)
            if verification_data.get('response_code') not in ESEWA_SUCCESS_CODES:
                logger.error(
                    'Received an error (%s) from Esewa merchant notification [%s]',
                    verification_data.get('response_code'),
                    request.POST
                )
                return redirect(reverse('payment_error'))
            reference_number = verification_data.get('reference_no')
            basket_id = OrderNumberGenerator().basket_id(reference_number)
            basket = self._get_basket(basket_id)
            transaction_id = verification_data.get('transaction_id')
            if not basket:
                logger.error('Received payment for non-existent basket [%s].', basket_id)
                return redirect(reverse('payment_error'))
        finally:
            payment_processor_response = self.payment_processor.record_processor_response(
                request.POST, transaction_id=transaction_id, basket=basket
            )

        try:
            with transaction.atomic():
                try:
                    self.handle_payment(verification_data, basket)
                except Exception as exc:
                    logger.exception(
                        'ESEWA payment did not complete for basket [%d] because of [%s]. '
                        'The payment response was recorded in entry [%d].',
                        basket.id,
                        exc.__class__.__name__,
                        payment_processor_response.id
                    )
                    raise
        except Exception as exc:  
            logger.exception(
                'Attempts to handle payment for basket [%d] failed due to [%s].',
                basket.id,
                exc.__class__.__name__
            )
            return redirect(reverse('payment_error'))
        
        self.create_order(request, basket)
        receipt_url = get_receipt_page_url(
            order_number=basket.order_number,
            site_configuration=basket.site.siteconfiguration
        )
        return redirect(receipt_url)
