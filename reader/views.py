from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import PDFUploadForm
from .models import ReaderDocument


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