from django.contrib import admin

from payouts.models import PayoutRequest


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("id", "recipient_details")
    readonly_fields = ("id", "created_at", "updated_at")

    def get_readonly_fields(
        self, request: object, obj: PayoutRequest | None = None
    ) -> tuple[str, ...]:
        base = ("id", "created_at", "updated_at")
        if obj is not None and obj.status in (
            PayoutRequest.Status.COMPLETED,
            PayoutRequest.Status.FAILED,
        ):
            return base + ("status",)
        return base
