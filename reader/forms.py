from django import forms
from .models import ReaderDocument, Note



class PDFUploadForm(forms.ModelForm):
    class Meta:
        model = ReaderDocument
        fields = ["pdf_file"]

        labels = {
            "pdf_file": "Choose a PDF document",
        }

        widgets = {
            "pdf_file": forms.FileInput(
                attrs={
                    "accept": ".pdf,application/pdf",
                    "class": "form-control",
                }
            ),
        }

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data["pdf_file"]

        # Limit uploads to 20 MB.
        if pdf_file.size > 20 * 1024 * 1024:
            raise forms.ValidationError(
                "The PDF must be 20 MB or smaller."
            )

        # Check the extension.
        if not pdf_file.name.lower().endswith(".pdf"):
            raise forms.ValidationError(
                "Please select a PDF file."
            )

        # Check the PDF signature.
        if pdf_file.read(5) != b"%PDF-":
            raise forms.ValidationError(
                "This file does not appear to be a valid PDF."
            )

        pdf_file.seek(0)
        return pdf_file






class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["title", "text"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Note title",
                }
            ),
            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 10,
                    "placeholder": "Write your note here...",
                }
            ),
        }




