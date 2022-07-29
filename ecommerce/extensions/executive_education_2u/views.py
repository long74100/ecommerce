

# pylint: disable=no-else-return


import logging
from functools import cached_property

from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.utils.translation import ugettext as _
from oscar.core.loading import get_class, get_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response

from ecommerce.extensions.api_client.get_smarter import GetSmarterEnterpriseApiClient
from ecommerce.extensions.basket.utils import apply_offers_on_basket, prepare_basket
from ecommerce.extensions.order.exceptions import AlreadyPlacedOrderException
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from ecommerce.enterprise.utils import (
    has_enterprise_offer,
)

import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import RedirectView
from oscar.apps.checkout.views import *  # pylint: disable=wildcard-import, unused-wildcard-import
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import (
    get_lms_course_about_url,
    get_lms_program_dashboard_url
)
from ecommerce.enterprise.utils import has_enterprise_offer
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.utils import get_program_uuid

logger = logging.getLogger(__name__)
Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
StockRecord = get_model('partner', 'StockRecord')


SUPPORTED_OFFER_TYPES = [ConditionalOffer.SITE]


class ExecutiveEducation2UViewSet(viewsets.ViewSet):
    permission_classes = (LoginRedirectIfUnauthenticated,)

    TERMS_CACHE_TIMEOUT = 60 * 15
    TERMS_CACHE_KEY = 'executive-education-terms'


    @cached_property
    def get_smarter_client(self):
        return GetSmarterEnterpriseApiClient()

    @cache_response(
        TERMS_CACHE_TIMEOUT,
        key_func=lambda *args, **kwargs: ExecutiveEducation2UViewSet.TERMS_CACHE_KEY,
        cache_errors=False,
    )
    @action(detail=False, methods=['get'], url_path='terms')
    def get_terms_and_conditions(self, request):
        """
        Fetch and return the terms and conditions.
        """
        try:
            terms = self.get_smarter_client.get_terms_and_conditions()
            return Response(terms)
        except Exception as ex:
            logger.exception(ex)
            return Response('Failed to retrieve terms and conditions.', status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _user_already_placed_order(self, user, product):
        return Order.objects.filter(user=user, lines__product=product).exists()

    def _get_executive_education_2u_product(self, partner, sku):
        product = Product.objects.filter(
            stockrecords__partner=partner, stockrecords__partner_sku=sku
        ).first()

        if product:
            certificate_type = getattr(product.attr, 'certificate_type', '')

            if certificate_type == 'paid-executive-education':
                return product

        return None

    @action(detail=False, methods=['get', 'post'], url_path='checkout')
    def checkout(self, request):
        partner = get_partner_for_site(request)

        if request.method == 'GET':
            sku = request.query_params.get('sku','').lower()

            if not sku:
                return HttpResponseBadRequest("SKU not provided.")

            product = self._get_executive_education_2u_product(partner, sku)
            if not product:
                return HttpResponseNotFound(f"No Executive Education (2U) product found for SKU {sku}.")

            if self._user_already_placed_order(request.user, product):
                # redirect to order page
                return HttpResponseRedirect('https://www.yahoo.com')
            try:
                basket = prepare_basket(request, [product])
                apply_offers_on_basket(request, basket)

                if basket.total_excl_tax != 0:
                    # They can't purchase this exec ed product
                    return HttpResponseRedirect('https://www.yahoo.com')
            except AlreadyPlacedOrderException:
                # Redirect to order page
                return HttpResponseRedirect('https://www.yahoo.com')
        if request.method == 'POST':

            basket = Basket.get_basket(request.user, request.site)

            breakpoint()
            if not basket.is_empty:
                Applicator().apply(basket, request.user, request)
                if basket.total_incl_tax != Decimal(0):
                    raise BasketNotFreeError(
                        'Basket [{}] is not free. User affected [{}]'.format(
                            basket.id,
                            basket.owner.id
                        )
                    )

                self.place_free_order(basket)

                # If a user's basket is empty redirect the user to the basket summary
                # page which displays the appropriate message for empty baskets.
                url = reverse('basket:summary')


            return HttpResponseRedirect('https://www.google.com')