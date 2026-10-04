from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = True


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'goods', 'buyer', 'seller', 'status', 'last_message', 'updated_at')
    list_filter = ('status',)
    search_fields = ('goods__title', 'buyer__email', 'seller__email')
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'msg_type', 'content', 'created_at')
    list_filter = ('msg_type',)
    search_fields = ('content', 'sender__email')