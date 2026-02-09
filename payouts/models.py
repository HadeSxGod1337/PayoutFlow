import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

# Allowed currency codes (must match COMMON_CURRENCIES in serializers).
ALLOWED_CURRENCIES = ("RUB", "USD", "EUR", "GBP", "KZT")


class PayoutRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3)
    recipient_details = models.JSONField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    STATUS_VALID_VALUES = frozenset(Status.values)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payout request"
        verbose_name_plural = "Payout requests"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"]
                ),
                name="payout_request_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(currency__in=ALLOWED_CURRENCIES),
                name="payout_request_allowed_currency",
            ),
        ]

    def __str__(self) -> str:
        return f"PayoutRequest {self.id} ({self.status})"


class IdempotencyRecord(models.Model):
    """Stores idempotency key -> payout mapping for POST /api/payouts/ (24h TTL)."""

    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    request_hash = models.CharField(
        max_length=64, help_text="Hash of request body for replay detection"
    )
    payout = models.OneToOneField(
        PayoutRequest,
        on_delete=models.CASCADE,
        related_name="idempotency_record",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Idempotency record"
        verbose_name_plural = "Idempotency records"


class PayoutAuditLog(models.Model):
    """Audit log for payout status changes (and delete) for compliance."""

    payout_id = models.UUIDField(db_index=True)  # not FK to allow log after payout delete
    action = models.CharField(max_length=32)  # e.g. status_change, delete
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Payout audit log"
        verbose_name_plural = "Payout audit logs"
