"""
URLs for esewa.
"""
from django.urls import path  # pylint: disable=unused-import
from django.views.generic import TemplateView  # pylint: disable=unused-import

urlpatterns = [
    # TODO: Fill in URL patterns and views here.
    path('/esewa/', TemplateView.as_view(template_name="esewa/base.html")),
]
