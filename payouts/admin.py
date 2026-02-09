from django.contrib import admin

from payouts.models import PayoutRequest


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("id", "recipient_details")
    readonly_fields = ("id", "created_at", "updated_at")
