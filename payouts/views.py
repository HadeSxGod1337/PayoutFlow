import logging

from django.db.models import QuerySet
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from payouts.models import PayoutRequest
from payouts.serializers import PayoutRequestSerializer
from payouts.tasks import process_payout_request
from payouts.utils import format_choices_error

logger = logging.getLogger(__name__)


class PayoutRequestViewSet(viewsets.ModelViewSet[PayoutRequest]):
    serializer_class = PayoutRequestSerializer
    lookup_field = "id"
    lookup_value_regex = "[0-9a-f-]+"

    def _get_status_param(self) -> str | None:
        return self.request.query_params.get("status")

    def list(self, request: Request, *args: object, **kwargs: object) -> Response:
        status_param = self._get_status_param()
        if status_param is not None and status_param not in PayoutRequest.STATUS_VALID_VALUES:
            logger.warning(
                "Invalid status filter: %r",
                status_param if len(status_param) <= 100 else status_param[:100] + "...",
            )
            return Response(
                {
                    "status": [
                        format_choices_error(
                            "Invalid status. Must be one of",
                            PayoutRequest.STATUS_VALID_VALUES,
                        )
                    ]
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return super().list(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[PayoutRequest]:
        qs = PayoutRequest.objects.all()
        status = self._get_status_param()
        if status and status in PayoutRequest.STATUS_VALID_VALUES:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer: BaseSerializer[PayoutRequest]) -> None:
        instance = serializer.save()
        logger.info(
            "Payout created: id=%s amount=%s currency=%s",
            instance.id,
            instance.amount,
            instance.currency,
        )
        process_payout_request.delay(str(instance.id))
