from django.conf import settings
from django.db import models


class ReaderDocument(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reader_documents",
    )
    title = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to="pdfs/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title




class Bookmark(models.Model):
    document = models.ForeignKey(
        "reader.ReaderDocument",
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reader_bookmarks",
    )
    page_number = models.PositiveIntegerField()
    label = models.CharField(max_length=150, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["page_number", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "user", "page_number"],
                name="unique_bookmark_per_document_page",
            )
        ]

    def __str__(self):
        return self.label or f"Page {self.page_number}"



    