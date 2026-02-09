import logging
from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from payouts.models import IdempotencyRecord, PayoutRequest
from payouts.serializers import PayoutRequestSerializer
from payouts.tasks import process_payout_request
from payouts.utils import (
    format_choices_error,
    hash_request_body,
    log_payout_delete,
    log_payout_status_change,
)

logger = logging.getLogger(__name__)

IDEMPOTENCY_KEY_HEADER = "HTTP_IDEMPOTENCY_KEY"
IDEMPOTENCY_KEY_TTL_HOURS = 24
IDEMPOTENCY_KEY_MAX_LENGTH = 255


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

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        idempotency_key = (request.META.get(IDEMPOTENCY_KEY_HEADER) or "").strip()
        if idempotency_key:
            if len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
                return Response(
                    {"detail": "Idempotency-Key header is too long."},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )
            request_hash = hash_request_body(request.data)
            threshold = timezone.now() - timedelta(hours=IDEMPOTENCY_KEY_TTL_HOURS)
            record = (
                IdempotencyRecord.objects.filter(
                    idempotency_key=idempotency_key,
                    created_at__gte=threshold,
                )
                .select_related("payout")
                .first()
            )
            if record is not None:
                if record.request_hash != request_hash:
                    return Response(
                        {"detail": "Idempotency-Key replay with different request body."},
                        status=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )
                serializer = self.get_serializer(record.payout)
                return Response(serializer.data, status=http_status.HTTP_200_OK)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        if instance is None:
            raise RuntimeError("perform_create did not set serializer.instance")
        if idempotency_key:
            IdempotencyRecord.objects.create(
                idempotency_key=idempotency_key,
                request_hash=hash_request_body(request.data),
                payout=instance,
            )
        return Response(serializer.data, status=http_status.HTTP_201_CREATED)

    def perform_create(self, serializer: BaseSerializer[PayoutRequest]) -> None:
        instance = serializer.save()
        logger.info(
            "Payout created: id=%s amount=%s currency=%s",
            instance.id,
            instance.amount,
            instance.currency,
        )
        process_payout_request.delay(str(instance.id))

    def perform_update(self, serializer: BaseSerializer[PayoutRequest]) -> None:
        instance = serializer.instance
        if instance is None:
            raise RuntimeError("perform_update called without instance")
        old_status = instance.status
        serializer.save()
        if "status" in serializer.validated_data:
            new_status = serializer.validated_data["status"]
            if old_status != new_status:
                log_payout_status_change(instance.id, old_status, new_status)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        instance = self.get_object()
        if instance.status in (
            PayoutRequest.Status.COMPLETED,
            PayoutRequest.Status.FAILED,
        ):
            return Response(
                {
                    "detail": "Cannot delete payout with status COMPLETED or FAILED (audit compliance)."
                },
                status=http_status.HTTP_403_FORBIDDEN,
            )
        log_payout_delete(instance.id, instance.status)
        self.perform_destroy(instance)
        return Response(status=http_status.HTTP_204_NO_CONTENT)
