from django.contrib import admin
from .models import ReaderDocument, ReaderPage, Bookmark, Note


class ReaderPageInline(admin.TabularInline):
    model = ReaderPage
    extra = 0
    fields = ("page_number", "original_text", "text", "updated_at")
    readonly_fields = ("updated_at",)
    ordering = ("page_number",)


class BookmarkInline(admin.TabularInline):
    model = Bookmark
    extra = 0
    fields = ("user", "page_number", "label", "created_at")
    readonly_fields = ("created_at",)


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    fields = ("user", "title", "text", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReaderDocument)
class ReaderDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "uploaded_at")
    list_filter = ("uploaded_at",)
    search_fields = ("title", "user__username", "user__email")
    readonly_fields = ("uploaded_at",)
    inlines = [ReaderPageInline, BookmarkInline, NoteInline]


@admin.register(ReaderPage)
class ReaderPageAdmin(admin.ModelAdmin):
    list_display = ("document", "page_number", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("document__title", "text", "original_text")
    readonly_fields = ("updated_at",)


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("label", "document", "user", "page_number", "created_at")
    list_filter = ("created_at",)
    search_fields = ("label", "document__title", "user__username")
    readonly_fields = ("created_at",)


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("title", "document", "user", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("title", "text", "document__title", "user__username")
    readonly_fields = ("created_at", "updated_at")


    