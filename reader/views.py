from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import PDFUploadForm
from .models import ReaderDocument

from .services.pdf_extractor import extract_pdf_pages

import logging

logger = logging.getLogger(__name__)

@login_required
def document_list(request):
    if request.method == "POST":
        form = PDFUploadForm(request.POST, request.FILES)

        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user

            # Use the uploaded filename as the document title.
            document.title = document.pdf_file.name.split("/")[-1]
            document.save()

            messages.success(
                request,
                "PDF uploaded successfully."
            )
            return redirect("reader:document_list")
    else:
        form = PDFUploadForm()

    documents = ReaderDocument.objects.filter(
        user=request.user
    ).order_by("-uploaded_at")

    return render(
        request,
        "reader/document_list.html",
        {
            "form": form,
            "documents": documents,
        },
    )




@login_required
def document_detail(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    pages = []
    error = None
    selected_mode = "normal"

    if request.method == "POST":
        selected_mode = request.POST.get("scan_mode", "normal")

        if selected_mode not in ("normal", "hard"):
            selected_mode = "normal"
            error = "Please select a valid scan mode."
        else:
            try:
                document.pdf_file.open("rb")
                try:
                    pdf_bytes = document.pdf_file.read()
                finally:
                    document.pdf_file.close()

                pages = extract_pdf_pages(
                    pdf_bytes,
                    mode=selected_mode,
                )

            except Exception:
                logger.exception(
                    "PDF extraction failed: document_id=%s, mode=%s",
                    document.pk,
                    selected_mode,
                )

                error = (
                    "We couldn't process this PDF. "
                    "Please try again or contact support."
                )

    return render(
        request,
        "reader/document_detail.html",
        {
            "document": document,
            "pages": pages,
            "error": error,
            "selected_mode": selected_mode,
        },
    )
