from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payouts.views import PayoutRequestViewSet

router = DefaultRouter()
router.register(r"payouts", PayoutRequestViewSet, basename="payout")

urlpatterns = [
    path("", include(router.urls)),
]
