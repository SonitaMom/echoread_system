from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .forms import PDFUploadForm
from .models import ReaderDocument, ReaderPage, Bookmark, Note
from .services.pdf_extractor import extract_pdf_pages
import logging
import asyncio
import json
import edge_tts
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
import fitz
from django.urls import reverse
from django.db import transaction
from .forms import NoteForm
from .services.ai import generate_note
from .services.ai_scan import scan_pdf


logger = logging.getLogger(__name__)

@login_required
def document_list(request):
    if request.method == "POST":
        form = PDFUploadForm(request.POST, request.FILES)

        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user

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

    error = None
    selected_mode = "normal"

    if request.method == "POST":
        selected_mode = request.POST.get("scan_mode", "normal")

        if selected_mode not in ("normal", "hard"):
            error = "Please select a valid scan mode."
        else:
            try:
                document.pdf_file.open("rb")
                try:
                    pdf_bytes = document.pdf_file.read()
                finally:
                    document.pdf_file.close()

                extracted_pages = extract_pdf_pages(
                    pdf_bytes,
                    mode=selected_mode,
                )

                for extracted in extracted_pages:
                    ReaderPage.objects.update_or_create(
                        document=document,
                        page_number=extracted["page_number"],
                        defaults={
                            "original_text": extracted["text"],
                            "text": extracted["text"],
                        },
                    )

                    if not created:
                        # Update the extracted original, but preserve
                        # the user's previously edited text.
                        saved_page.original_text = extracted["text"]
                        saved_page.save(
                            update_fields=["original_text"]
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

    pages = ReaderPage.objects.filter(
        document=document,
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
            "notes": Note.objects.filter(
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







@login_required
def edit_reader(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    error = None
    session_key = f"reader_scan_preview_{document.pk}"

    if request.method == "POST":
        selected_mode = request.POST.get("scan_mode")

        if selected_mode not in ("normal", "hard", "ai"):
            error = "Invalid scan mode."
        else:
            try:
                document.pdf_file.open("rb")
                try:
                    pdf_bytes = document.pdf_file.read()
                finally:
                    document.pdf_file.close()

                if selected_mode == "ai":
                    preview_pages = scan_pdf(pdf_bytes)

                    with fitz.open(
                        stream=pdf_bytes,
                        filetype="pdf",
                    ) as pdf:
                        expected_pages = len(pdf)

                    if not isinstance(preview_pages, list):
                        raise ValueError(
                            "Invalid AI Scan response."
                        )

                    page_map = {}

                    for item in preview_pages:
                        if not isinstance(item, dict):
                            raise ValueError(
                                "Invalid page result."
                            )

                        page_number = item.get("page_number")
                        page_text = item.get("text")

                        if (
                            not isinstance(page_number, int)
                            or isinstance(page_number, bool)
                            or not 1 <= page_number <= expected_pages
                            or page_number in page_map
                            or not isinstance(page_text, str)
                        ):
                            raise ValueError(
                                "Invalid AI Scan page data."
                            )

                        page_map[page_number] = page_text

                    expected_numbers = set(
                        range(1, expected_pages + 1)
                    )

                    if set(page_map) != expected_numbers:
                        raise ValueError(
                            "AI Scan missed one or more pages."
                        )

                    preview_pages = [
                        {
                            "page_number": number,
                            "text": page_map[number],
                        }
                        for number in range(
                            1, expected_pages + 1
                        )
                    ]

                else:
                    preview_pages = extract_pdf_pages(
                        pdf_bytes,
                        mode=selected_mode,
                    )

                # Preview only; do not modify ReaderPage.
                request.session[session_key] = preview_pages

                return redirect(
                    "reader:edit_reader",
                    pk=document.pk,
                )

            except Exception:
                logger.exception(
                    "PDF processing failed: document_id=%s, mode=%s",
                    document.pk,
                    selected_mode,
                )
                error = (
                    "We couldn't process this PDF. "
                    "Please try again or check the server logs."
                )

    preview_pages = request.session.get(session_key)

    if (
        request.method == "GET"
        and request.GET.get("discard_preview") == "1"
    ):
        request.session.pop(session_key, None)
        preview_pages = None

    if preview_pages is not None:
        pages = [
            {
                "page_number": item["page_number"],
                "text": item["text"],
            }
            for item in preview_pages
        ]
    else:
        pages = list(
            ReaderPage.objects.filter(
                document=document
            )
        )

    return render(
        request,
        "reader/edit_reader.html",
        {
            "document": document,
            "pages": pages,
            "error": error,
            "has_unsaved_scan": preview_pages is not None,
        },
    )



@login_required
def save_reader(request, pk):
    if request.method != "POST":
        return redirect("reader:edit_reader", pk=pk)

    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    session_key = f"reader_scan_preview_{document.pk}"
    preview_pages = request.session.get(session_key)

    try:
        with transaction.atomic():
            if preview_pages is not None:
                # Save the scanned text as the new original and edited text.
                for item in preview_pages:
                    ReaderPage.objects.update_or_create(
                        document=document,
                        page_number=item["page_number"],
                        defaults={
                            "original_text": item["text"],
                            "text": request.POST.get(
                                f"page_{item['page_number']}",
                                item["text"],
                            ),
                        },
                    )
            else:
                # Save edits to existing pages.
                pages = ReaderPage.objects.filter(
                    document=document
                )

                for page in pages:
                    field_name = f"page_{page.page_number}"

                    if field_name not in request.POST:
                        raise ValueError(
                            f"Missing text for page {page.page_number}."
                        )

                    page.text = request.POST[field_name]
                    page.save(update_fields=["text", "updated_at"])

    except Exception:
        logger.exception(
            "Failed to save reader: document_id=%s",
            document.pk,
        )
        messages.error(request, "Could not save your changes.")
        return redirect("reader:edit_reader", pk=document.pk)

    # Clear the temporary scan only after a successful database save.
    if preview_pages is not None:
        del request.session[session_key]
        request.session.modified = True

    messages.success(request, "Your changes have been saved.")
    return redirect("/home/")








@login_required
def new_reader(request):
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            messages.error(request, "Please select a PDF file.")
            return render(request, "reader/new_reader.html")

        if not pdf_file.name.lower().endswith(".pdf"):
            messages.error(request, "Please upload a PDF file.")
            return render(request, "reader/new_reader.html")

        document = ReaderDocument.objects.create(
            user=request.user,
            title=pdf_file.name,
            pdf_file=pdf_file,
        )

        return redirect(
            "reader:document_detail",
            pk=document.pk,
        )

    return render(request, "reader/new_reader.html")








@login_required
def create_note(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        form = NoteForm(request.POST)

        if form.is_valid():
            note = form.save(commit=False)
            note.document = document
            note.user = request.user
            note.save()

            messages.success(request, "Note created successfully.")
            return redirect(
                "reader:document_detail",
                pk=document.pk,
            )
    else:
        form = NoteForm()

    return render(
        request,
        "reader/note_form.html",
        {
            "document": document,
            "form": form,
            "page_title": "Create Note",
        },
    )


@login_required
def edit_note(request, pk, note_id):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )
    note = get_object_or_404(
        Note,
        pk=note_id,
        document=document,
        user=request.user,
    )

    if request.method == "POST":
        form = NoteForm(request.POST, instance=note)

        if form.is_valid():
            form.save()
            messages.success(request, "Note updated successfully.")
            return redirect(
                "reader:document_detail",
                pk=document.pk,
            )
    else:
        form = NoteForm(instance=note)

    return render(
        request,
        "reader/note_form.html",
        {
            "document": document,
            "form": form,
            "page_title": "Edit Note",
        },
    )


@login_required
def delete_note(request, pk, note_id):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )
    note = get_object_or_404(
        Note,
        pk=note_id,
        document=document,
        user=request.user,
    )

    if request.method == "POST":
        note.delete()
        messages.success(request, "Note deleted.")
        return redirect(
            "reader:document_detail",
            pk=document.pk,
        )

    return redirect(
        "reader:document_detail",
        pk=document.pk,
    )









@login_required
@require_POST
def save_note_ajax(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    note_id = request.POST.get("note_id")
    title = request.POST.get("title", "").strip()
    text = request.POST.get("text", "").strip()

    if not title or not text:
        return JsonResponse(
            {
                "success": False,
                "error": "Title and text are required.",
            },
            status=400,
        )

    if note_id:
        note = get_object_or_404(
            Note,
            pk=note_id,
            document=document,
            user=request.user,
        )
        note.title = title
        note.text = text
        note.save(update_fields=["title", "text", "updated_at"])
    else:
        note = Note.objects.create(
            document=document,
            user=request.user,
            title=title,
            text=text,
        )

    return JsonResponse({
        "success": True,
        "note": {
            "id": note.pk,
            "title": note.title,
            "text": note.text,
        },
    })





@login_required
@require_POST
def delete_note_ajax(request, pk, note_id):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    note = get_object_or_404(
        Note,
        pk=note_id,
        document=document,
        user=request.user,
    )

    note.delete()

    return JsonResponse({"success": True})










@login_required
@require_POST
def ask_ai_ajax(request, pk):
    document = get_object_or_404(
        ReaderDocument,
        pk=pk,
        user=request.user,
    )

    question = request.POST.get("question", "").strip()

    if not question:
        return JsonResponse(
            {"success": False, "error": "Please enter a question."},
            status=400,
        )

    if len(question) > 2000:
        return JsonResponse(
            {"success": False, "error": "Your question is too long."},
            status=400,
        )

    pages = ReaderPage.objects.filter(document=document).order_by(
        "page_number"
    )

    document_text = "\n\n".join(
        f"Page {page.page_number}:\n{page.text}"
        for page in pages
        if page.text.strip()
    )

    if not document_text:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "This PDF has no saved extracted text yet. "
                    "Scan the PDF before asking AI."
                ),
            },
            status=400,
        )

    # Keep requests bounded to avoid sending an excessively large context.
    document_text = document_text[:60000]

    try:
        result = generate_note(question, document_text)
    except RuntimeError as exc:
        return JsonResponse(
            {"success": False, "error": str(exc)},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected AI error for document %s", document.pk)
        return JsonResponse(
            {
                "success": False,
                "error": "AI couldn't answer right now. Please try again.",
            },
            status=502,
        )

    # Save automatically only after generation succeeds.
    note = Note.objects.create(
        document=document,
        user=request.user,
        title=result["title"][:200],
        text=result["text"],
    )

    return JsonResponse({
        "success": True,
        "note": {
            "id": note.pk,
            "title": note.title,
            "text": note.text,
        },
    })













