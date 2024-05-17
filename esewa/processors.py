import logging
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import clean_field_value

logger = logging.getLogger(__name__)

def format_price(price):
    """
    Return the price in the expected format.
    """
    return '{:0.2f}'.format(price)

class esewaPayException(GatewayError):
     """
    An umbrella exception to catch all errors from HyperPay.
    """
     pass  # pylint: disable=unnecessary-pass

class esewa (BasePaymentProcessor) :
       """
    Esewa payment processor.

    For reference, see https://developer.esewa.com.np/pages/Epay
    """
       
Name= 'esewa'

def __init__ (self, site) :
     super(esewa, self).__init__(site)
     configuration = self.configuration
     self.merchant_id = configuration['merchant_id']
     self.secret_key = configuration['secret_key']
     self.base_url = configuration['base_url']

     self.site = site

def _get_user_profile_data(self, user, request):
      """
        Returns the profile data fields for the given user.
        """
      def get_extended_profile_field (account_details, field_name, default_value= None):
           """
            Helper function to get the values of extended profile fields.
            """
           return next(
                (
                    field.get('field_value', default_value) for field in account_details['extended_profile']
                    if field['field_name'] == field_name
                ),
                default_value
           )
      user_account_details = user.account_details(request)
      data = {
            'customer.email': user.email,
        }
      first_name = get_extended_profile_field(user_account_details, 'first_name', '')
      if first_name:
            data['customer.givenName'] = first_name
            data['customer.surname'] = get_extended_profile_field(user_account_details, 'last_name', '')
      else:
            logger.warning('Unable to get the first name and last name for the user %s', user.username)

      return data

def _get_basket_data(self, basket):
        """
        Return the basket data
        """

        def get_cart_field(index, name):
            """
            Return the cart field name.
            """
            return 'cart.items[{}].{}'.format(index, name)

        basket_data = {
            'amount': format_price(basket.total_incl_tax),
            'currency': self.currency,
            'merchantTransactionId': basket.order_number
        }
        for index, line in enumerate(basket.all_lines()):
            cart_item = {
                get_cart_field(index, 'name'): clean_field_value(line.product.title),
                get_cart_field(index, 'quantity'): line.quantity,
                get_cart_field(index, 'type'): self.CART_ITEM_TYPE_DIGITAL,
                get_cart_field(index, 'sku'): line.stockrecord.partner_sku,
                get_cart_field(index, 'price'): format_price(line.unit_price_incl_tax),
                get_cart_field(index, 'totalAmount'): format_price(line.line_price_incl_tax_incl_discounts)
            }
            basket_data.update(cart_item)
        return basket_data

def _get_course_id_title(self, line):
        """
        Return the line title prefixed with the course ID, if available.
        """
        course_id = ''
        line_course = line.product.course
        if line_course:
            course_id = '{}|'.format(line_course.id)
        return course_id + line.product.title
def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Return the transaction parameters needed for eSewa payment.
        """
        # Retrieve necessary information from the basket, request, and configuration
        # Adjust the parameters according to eSewa's requirements
        
        # Example eSewa API endpoint and request parameters
        endpoint = "https://uat.esewa.com.np"
        payload = {
            'amount': str(basket.total_incl_tax),
            'failure_url' : self.failure_url,
            'product_delivery_charge' : self.product_delivery_charge,
            'product_code' : self.product_code,
            'signature' : self.signature,
            'signed_field_names': self.signed_field_names,
            'success_url': self.success_url,
            'tax_amount' : self.tax_amount,
            'total_amount' : str(basket.total_incl_tax),
            'transaction_uuid' : self.transaction_uuid,
            # Add other required parameters
        }

        # Make a POST request to eSewa API to create payment
        response = requests.post(endpoint, data=payload)
        
        # Process the response and extract necessary data
        # Adjust this according to eSewa's response structure
        
        # Example response handling
        payment_url = response.json().get('payment_url')

        return {
            'payment_page_url': payment_url
        }


def handle_processor_response(self, response, basket=None):
        """
        Handle the eSewa processor response.
        """
        # Process the response from eSewa
        # Extract transaction details and handle success or failure
        
        # Example handling for successful transaction
        transaction_uuid = response.get('transaction_id')
        total_amount = response.get('total_amount')
        product_code = response.get('product_code')
        status = response.get('status')
        ref_id = response.get('ref_id')  # Assuming Nepalese Rupee
        
        
        # Return processed response
        return HandledProcessorResponse(
            transaction_uuid=transaction_uuid,
            total_amount=total_amount,
            product_code=product_code,
            status=status,
            ref_id=ref_id
        )

def issue_credit(self, order_number, basket, reference_number, amount, currency):
        """
        This is currently not implemented.

        While esewa supports this ('refund url') this endpoint is not available
        for demo merchants.
        """
        logger.exception(
            'esewa processor cannot issue credits or refunds at the moment.'
        )

