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