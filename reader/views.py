from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import PDFUploadForm
from .models import ReaderDocument

from .services.pdf_extractor import extract_pdf_pages

import logging

import asyncio
import json

import edge_tts

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import ReaderDocument, Bookmark

import fitz




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

            "bookmarks": Bookmark.objects.filter(
                document=document,
                user=request.user,
            ),
            
        },
    )






@login_required
@require_POST
def text_to_speech(request, pk):
    # Ensure users can only generate audio for their own documents.
    get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    try:
        data = json.loads(request.body)

        text = data.get("text", "").strip()
        language = data.get("language", "auto")
        gender = data.get("voice", "male")

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400,
        )

    if not text:
        return JsonResponse(
            {"error": "No text was provided."},
            status=400,
        )

    # Keep requests to a reasonable size.
    if len(text) > 10000:
        return JsonResponse(
            {"error": "Please send a shorter passage."},
            status=400,
        )

    if language not in ("auto", "en", "km"):
        return JsonResponse(
            {"error": "Unsupported language selection."},
            status=400,
        )

    if gender not in ("male", "female"):
        return JsonResponse(
            {"error": "Unsupported voice selection."},
            status=400,
        )

    # Simple language detection for English and Khmer.
    if language == "auto":
        contains_khmer = any(
            "\u1780" <= char <= "\u17ff"
            for char in text
        )
        language = "km" if contains_khmer else "en"

    voices = {
        "en": {
            "male": "en-US-GuyNeural",
            "female": "en-US-JennyNeural",
        },
        "km": {
            "male": "km-KH-PisethNeural",
            "female": "km-KH-SreymomNeural",
        },
    }

    voice = voices[language][gender]

    async def generate_audio():
        communicator = edge_tts.Communicate(
            text=text,
            voice=voice,
        )

        audio_chunks = []

        async for chunk in communicator.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        return b"".join(audio_chunks)

    try:
        audio_bytes = asyncio.run(generate_audio())

        if not audio_bytes:
            return JsonResponse(
                {"error": "No audio was generated."},
                status=502,
            )

        response = HttpResponse(
            audio_bytes,
            content_type="audio/mpeg",
        )
        response["Cache-Control"] = "no-store"
        return response

    except Exception:
        logger.exception(
            "TTS generation failed for document_id=%s",
            pk,
        )
        return JsonResponse(
            {"error": "Audio generation failed. Please try again."},
            status=502,
        )







@login_required
@require_POST
def create_bookmark(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    try:
        data = json.loads(request.body)
        page_number = int(data.get("page_number", 0))
        label = str(data.get("label", "")).strip()
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse(
            {"error": "Invalid bookmark details."},
            status=400,
        )

    if page_number < 1:
        return JsonResponse(
            {"error": "Page number must be at least 1."},
            status=400,
        )

    if len(label) > 150:
        return JsonResponse(
            {"error": "Bookmark label must be 150 characters or fewer."},
            status=400,
        )

    # Check the actual number of pages in the PDF.
    try:
        document.pdf_file.open("rb")
        try:
            pdf_bytes = document.pdf_file.read()
        finally:
            document.pdf_file.close()

        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf:
            total_pages = pdf.page_count
    except Exception:
        return JsonResponse(
            {"error": "Could not read this PDF."},
            status=400,
        )

    if page_number > total_pages:
        return JsonResponse(
            {"error": f"This PDF has only {total_pages} pages."},
            status=400,
        )

    bookmark, created = Bookmark.objects.update_or_create(
        document=document,
        user=request.user,
        page_number=page_number,
        defaults={"label": label},
    )

    return JsonResponse({
        "id": bookmark.id,
        "page_number": bookmark.page_number,
        "label": bookmark.label,
        "display_name": bookmark.label or f"Page {bookmark.page_number}",
        "created": created,
    })


@login_required
@require_POST
def delete_bookmark(request, pk, bookmark_id):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    bookmark = get_object_or_404(
        Bookmark,
        pk=bookmark_id,
        document=document,
        user=request.user,
    )

    bookmark.delete()

    return JsonResponse({"success": True})


