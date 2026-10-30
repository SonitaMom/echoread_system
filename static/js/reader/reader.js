document.addEventListener("DOMContentLoaded", () => {
    const pages = [...document.querySelectorAll(".reader-page")];
    const audio = document.getElementById("reader-audio");

    const playButton = document.getElementById("play-reading");
    const pauseButton = document.getElementById("pause-reading");
    const stopButton = document.getElementById("stop-reading");
    const backButton = document.getElementById("back-10-seconds");
    const forwardButton = document.getElementById("forward-10-seconds");

    const speedSelect = document.getElementById("reading-speed");
    const languageSelect = document.getElementById("reading-language");
    const voiceSelect = document.getElementById("reading-voice");

    const status = document.getElementById("reading-status");
    const downloadButton = document.getElementById("download-mp3");
    const downloadStatus = document.getElementById("download-status");

    if (!pages.length || !audio || !audio.dataset.ttsUrl) {
        if (status) status.textContent = "The reader could not be initialized.";
        return;
    }

    const MAX_CHUNK_LENGTH = 9000;
    const PREFETCH_SECONDS = 8;
    const chunks = [];

    // Keep each chunk below the server's 10,000-character limit.
    pages.forEach((page, pageIndex) => {
        const pageText = page.querySelector(".reader-page-text")
            .textContent.trim();

        const paragraphs = pageText
            .split(/\n+/)
            .map(text => text.trim())
            .filter(Boolean);

        let buffer = "";

        function addChunk(text) {
            chunks.push({
                text,
                pageIndex,
                pageNumber: page.dataset.pageNumber,
            });
        }

        paragraphs.forEach(paragraph => {
            // Split unusually long paragraphs safely.
            while (paragraph.length > MAX_CHUNK_LENGTH) {
                if (buffer) {
                    addChunk(buffer);
                    buffer = "";
                }

                addChunk(paragraph.slice(0, MAX_CHUNK_LENGTH));
                paragraph = paragraph.slice(MAX_CHUNK_LENGTH);
            }

            const combined = buffer
                ? `${buffer}\n${paragraph}`
                : paragraph;

            if (combined.length > MAX_CHUNK_LENGTH) {
                if (buffer) addChunk(buffer);
                buffer = paragraph;
            } else {
                buffer = combined;
            }
        });

        if (buffer) addChunk(buffer);
    });

    let currentIndex = 0;
    let currentAudioUrl = null;

    function getSelectedPageNumber() {
        const pageInput = document.getElementById("page-number-input");
        const pageNumber = Number(pageInput?.value);

        if (
            !Number.isInteger(pageNumber) ||
            pageNumber < 1 ||
            pageNumber > pages.length
        ) {
            return 1;
        }

        return pageNumber;
    }

    function getFirstChunkIndexForPage(pageNumber) {
        return chunks.findIndex(
            chunk => Number(chunk.pageNumber) === pageNumber
        );
    }

    let requestVersion = 0;
    let isLoading = false;
    let downloadInProgress = false;

    // Cache generated audio blobs so prefetching and downloading can reuse them.
    const audioCache = new Map();

    function updateStatus(message) {
        status.textContent = message;
    }

    function showCurrentPage() {
    const chunk = chunks[currentIndex];
    if (!chunk) return;

    const pageNumber = Number(chunk.pageNumber);

    if (!Number.isInteger(pageNumber) || pageNumber < 1) return;

    pages.forEach((page, index) => {
        page.hidden = index !== pageNumber - 1;
    });
}

    function requestAudio(index) {
        if (audioCache.has(index)) {
            return audioCache.get(index);
        }

        const chunk = chunks[index];
        if (!chunk) return Promise.resolve(null);

        const promise = (async () => {
            const csrfToken = document.querySelector(
                "[name=csrfmiddlewaretoken]"
            )?.value;

            const response = await fetch(audio.dataset.ttsUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken || "",
                },
                body: JSON.stringify({
                    text: chunk.text,
                    language: languageSelect.value,
                    voice: voiceSelect.value,
                }),
            });

            if (!response.ok) {
                let message = "Audio generation failed.";

                try {
                    const result = await response.json();
                    if (result.error) message = result.error;
                } catch {
                    // Keep the default message.
                }

                throw new Error(message);
            }

            return response.blob();
        })();

        audioCache.set(index, promise);

        promise.catch(() => {
            if (audioCache.get(index) === promise) {
                audioCache.delete(index);
            }
        });

        return promise;
    }

    function prefetchNext() {
        const nextIndex = currentIndex + 1;
        if (nextIndex >= chunks.length) return;

        requestAudio(nextIndex).catch(() => {
            // Playback will report the error if this chunk is needed.
        });
    }

    function releaseCurrentUrl() {
        if (currentAudioUrl) {
            URL.revokeObjectURL(currentAudioUrl);
            currentAudioUrl = null;
        }
    }

    function cancelPlayback() {
        requestVersion++;
        isLoading = false;
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        releaseCurrentUrl();
    }

    async function playChunk(index = currentIndex) {
        if (index < 0 || index >= chunks.length) {
            updateStatus("Finished reading the document.");
            return;
        }

        currentIndex = index;
        const version = ++requestVersion;
        isLoading = true;

        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        releaseCurrentUrl();

        showCurrentPage();

        const chunk = chunks[currentIndex];

        updateStatus(
            `Preparing page ${chunk.pageNumber}, ` +
            `audio section ${currentIndex + 1} of ${chunks.length}...`
        );

        try {
            const blob = await requestAudio(currentIndex);

            if (version !== requestVersion) return;

            currentAudioUrl = URL.createObjectURL(blob);
            audio.src = currentAudioUrl;
            audio.playbackRate = Number(speedSelect.value);

            await audio.play();

            if (version !== requestVersion) return;

            isLoading = false;

            updateStatus(
                `Reading page ${chunk.pageNumber}, ` +
                `section ${currentIndex + 1} of ${chunks.length}.`
            );

            // Prepare the next section while this one is playing.
            prefetchNext();
        } catch (error) {
            if (version !== requestVersion) return;

            isLoading = false;
            updateStatus(error.message || "Unable to play this audio.");
        }
    }

    playButton.addEventListener("click", async () => {
        if (isLoading) return;

        // Resume the current audio if it was paused.
        if (audio.src && audio.paused && audio.currentTime > 0) {
            try {
                await audio.play();
                updateStatus("Reading resumed.");
            } catch {
                updateStatus("Unable to resume playback.");
            }
            return;
        }

        // Start reading from the page selected by the user.
        const selectedPage = getSelectedPageNumber();
        const selectedChunk = getFirstChunkIndexForPage(selectedPage);

        if (selectedChunk === -1) {
            updateStatus(`Page ${selectedPage} contains no readable text.`);
            return;
        }

        await playChunk(selectedChunk);
    });

    pauseButton.addEventListener("click", () => {
        if (!audio.paused) {
            audio.pause();
            updateStatus("Reading paused.");
        }
    });

    stopButton.addEventListener("click", () => {
        cancelPlayback();
        currentIndex = 0;
        updateStatus("Reading stopped.");
    });

    backButton.addEventListener("click", () => {
        if (!audio.src) {
            updateStatus("Start reading before seeking.");
            return;
        }

        audio.currentTime = Math.max(0, audio.currentTime - 10);
        updateStatus("Moved back 10 seconds.");
    });

    forwardButton.addEventListener("click", () => {
        if (!audio.src) {
            updateStatus("Start reading before seeking.");
            return;
        }

        if (Number.isFinite(audio.duration)) {
            if (audio.currentTime + 10 >= audio.duration) {
                if (currentIndex < chunks.length - 1) {
                    playChunk(currentIndex + 1);
                } else {
                    audio.currentTime = Math.max(0, audio.duration - 0.1);
                }
            } else {
                audio.currentTime += 10;
            }
        } else {
            audio.currentTime += 10;
        }

        updateStatus("Moved forward 10 seconds.");
    });

    speedSelect.addEventListener("change", () => {
        audio.playbackRate = Number(speedSelect.value);
        updateStatus(`Reading speed set to ${speedSelect.value}×.`);
    });

    function changeVoiceSetting() {
        // Previously generated audio uses the old voice/language.
        audioCache.clear();

        if (!audio.paused || isLoading) {
            playChunk(currentIndex);
        } else {
            updateStatus("Voice settings changed. Press Play to continue.");
        }
    }

    languageSelect.addEventListener("change", changeVoiceSetting);
    voiceSelect.addEventListener("change", changeVoiceSetting);

    // Start generating the next chunk before the current one ends.
    audio.addEventListener("timeupdate", () => {
        if (
            Number.isFinite(audio.duration) &&
            audio.duration - audio.currentTime <= PREFETCH_SECONDS
        ) {
            prefetchNext();
        }
    });

    audio.addEventListener("ended", () => {
        if (currentIndex < chunks.length - 1) {
            playChunk(currentIndex + 1);
        } else {
            updateStatus("Finished reading the document.");
        }
    });

    // Generate every chunk and combine them into a downloadable MP3.
    downloadButton.addEventListener("click", async () => {
        if (downloadInProgress) return;

        downloadInProgress = true;
        downloadButton.disabled = true;

        const originalLanguage = languageSelect.value;
        const originalVoice = voiceSelect.value;
        const blobs = [];

        try {
            for (let index = 0; index < chunks.length; index++) {
                downloadStatus.textContent =
                    `Generating audio: ${index + 1} of ${chunks.length}...`;

                blobs.push(await requestAudio(index));
            }

            const mp3Blob = new Blob(blobs, { type: "audio/mpeg" });
            const url = URL.createObjectURL(mp3Blob);
            const link = document.createElement("a");

            let filename = audio.dataset.documentName || "document";
            filename = filename.replace(/\.pdf$/i, "").trim();

            link.href = url;
            link.download = `${filename || "document"}.mp3`;
            document.body.appendChild(link);
            link.click();
            link.remove();

            URL.revokeObjectURL(url);
            downloadStatus.textContent = "MP3 download is ready.";
        } catch (error) {
            downloadStatus.textContent =
                error.message || "Unable to generate the MP3.";
        } finally {
            downloadInProgress = false;
            downloadButton.disabled = false;

            // Keep these references explicit: downloading uses the current
            // voice settings and does not change the reader's selections.
            void originalLanguage;
            void originalVoice;
        }
    });

    showCurrentPage();

    if (!chunks.length) {
        updateStatus("This document contains no readable text.");

        [
            playButton,
            pauseButton,
            stopButton,
            backButton,
            forwardButton,
            downloadButton,
        ].forEach(button => {
            button.disabled = true;
        });
    }


    /* =====================================
       Page Navigation and Bookmarks
    ===================================== */
    (() => {
        const pages = Array.from(
            document.querySelectorAll(".reader-page")
        );

        if (!pages.length) return;

        const pageInput = document.getElementById("page-number-input");
        const previousButton = document.getElementById("previous-page");
        const nextButton = document.getElementById("next-page");
        const pageStatus = document.getElementById("page-navigation-status");

        const bookmarkLabel = document.getElementById("bookmark-label");
        const addBookmarkButton = document.getElementById("add-bookmark");
        const bookmarkSelect = document.getElementById("bookmark-select");
        const bookmarkStatus = document.getElementById("bookmark-status");

        const deleteSelect = document.getElementById("delete-bookmark-select");
        const deleteButton = document.getElementById("delete-bookmark");
        const deleteStatus = document.getElementById("delete-bookmark-status");

        const audio = document.getElementById("reader-audio");

        if (
            !pageInput || !previousButton || !nextButton ||
            !pageStatus || !addBookmarkButton || !bookmarkSelect ||
            !deleteSelect || !deleteButton
        ) {
            console.error("Reader navigation or bookmark controls are missing.");
            return;
        }

        const bookmarkControls = document.querySelector(".bookmark-controls");
        const createBookmarkUrl = bookmarkControls.dataset.createUrl;
        const deleteBookmarkSection = document.querySelector(
            ".delete-bookmark-controls"
        );

        const deleteBookmarkUrlTemplate =
            deleteBookmarkSection?.dataset.deleteUrlTemplate;

        // These values are replaced below using data attributes on the page.
        // The document URL is supplied by the template.
        const totalPages = pages.length;
        let currentPage = 1;
        let pageInputTimer = null;

        pageInput.min = 1;
        pageInput.max = totalPages;
        pageInput.value = currentPage;
        pageStatus.textContent = `Page ${currentPage} of ${totalPages}`;

        function showPage(pageNumber) {
            if (
                !Number.isInteger(pageNumber) ||
                pageNumber < 1 ||
                pageNumber > totalPages
            ) {
                pageStatus.textContent =
                    `Enter a page number between 1 and ${totalPages}.`;
                return false;
            }

            currentPage = pageNumber;

            pages.forEach((page, index) => {
                const isCurrent = index + 1 === currentPage;
                page.hidden = !isCurrent;
            });

            pageInput.value = currentPage;
            pageStatus.textContent = `Page ${currentPage} of ${totalPages}`;

            return true;
        }

        previousButton.addEventListener("click", () => {
            showPage(currentPage - 1);
        });

        nextButton.addEventListener("click", () => {
            showPage(currentPage + 1);
        });

        function resetPageInput() {
            pageInput.value = currentPage;
            pageStatus.textContent = `Page ${currentPage} of ${totalPages}`;
        }

        pageInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                clearTimeout(pageInputTimer);

                const rawValue = pageInput.value.trim();
                const pageNumber = Number(rawValue);

                if (
                    rawValue === "" ||
                    !Number.isInteger(pageNumber) ||
                    pageNumber < 1 ||
                    pageNumber > totalPages
                ) {
                    resetPageInput();
                    return;
                }

                if (showPage(pageNumber)) {
                    pageInput.blur();
                }
            }
        });

        pageInput.addEventListener("blur", () => {
            clearTimeout(pageInputTimer);
            const rawValue = pageInput.value.trim();
            const pageNumber = Number(rawValue);

            if (
                rawValue === "" ||
                !Number.isInteger(pageNumber) ||
                pageNumber < 1 ||
                pageNumber > totalPages
            ) {
                resetPageInput();
                return;
            }

            showPage(pageNumber);
        });

        pageInput.addEventListener("input", () => {
            const rawValue = pageInput.value.trim();
            if (rawValue === "") return;

            const pageNumber = Number(rawValue);
            if (!Number.isInteger(pageNumber)) {
                return;
            }

            clearTimeout(pageInputTimer);

            pageInputTimer = setTimeout(() => {
                if (pageNumber < 1 || pageNumber > totalPages) {
                    resetPageInput();
                    return;
                }

                showPage(pageNumber);
            }, 500);
        });

        // Read the CSRF token used by Django.
        function getCsrfToken() {
            const input = document.querySelector(
                "[name=csrfmiddlewaretoken]"
            );

            if (input) return input.value;

            const cookie = document.cookie
                .split("; ")
                .find(item => item.startsWith("csrftoken="));

            return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
        }

        function refreshBookmarkOptions(bookmarks) {
            const selectors = [bookmarkSelect, deleteSelect];

            selectors.forEach(select => {
                const previousValue = select.value;

                select.replaceChildren();

                const placeholder = document.createElement("option");
                placeholder.value = "";
                placeholder.textContent = "Select a bookmark";
                select.appendChild(placeholder);

                bookmarks.forEach(bookmark => {
                    const option = document.createElement("option");

                    option.value = select === bookmarkSelect
                        ? bookmark.page_number
                        : bookmark.id;

                    option.dataset.bookmarkId = bookmark.id;

                    option.textContent = bookmark.label
                        ? `${bookmark.label} — Page ${bookmark.page_number}`
                        : `Page ${bookmark.page_number}`;

                    select.appendChild(option);
                });

                if (
                    Array.from(select.options).some(
                        option => option.value === previousValue
                    )
                ) {
                    select.value = previousValue;
                }
            });
        }

        async function loadBookmarks() {
            // The initial bookmark options are rendered by Django.
            // Reloading the page after changes refreshes them from the database.
            // We keep this function as a hook for a future bookmark-list endpoint.
        }

        bookmarkSelect.addEventListener("change", () => {
            if (!bookmarkSelect.value) return;

            const pageNumber = Number(bookmarkSelect.value);
            showPage(pageNumber);
        });

        addBookmarkButton.addEventListener("click", async () => {
            const label = bookmarkLabel.value.trim();

            addBookmarkButton.disabled = true;
            bookmarkStatus.textContent = "Saving bookmark…";

            try {
                const response = await fetch(createBookmarkUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken()
                    },
                    body: JSON.stringify({
                        page_number: currentPage,
                        label: label
                    })
                });

                // const data = await response.json();

                // if (!response.ok) {
                //     throw new Error(data.error || "Could not save bookmark.");
                // }



                const responseText = await response.text();

                let data;
                try {
                    data = JSON.parse(responseText);
                } catch {
                    console.error("Delete URL:", deleteUrl);
                    console.error("HTTP status:", response.status);
                    console.error("Server response:", responseText);

                    throw new Error(
                        `Server returned HTML instead of JSON (HTTP ${response.status}). Check the browser console.`
                    );
                }

                if (!response.ok) {
                    throw new Error(data.error || "Could not delete bookmark.");
                }





                bookmarkStatus.textContent =
                    `Bookmark saved: ${data.display_name}.`;

                // Reload to retrieve the updated bookmark list from Django.
                window.location.reload();
            } catch (error) {
                bookmarkStatus.textContent = error.message;
            } finally {
                addBookmarkButton.disabled = false;
            }
        });

        deleteButton.addEventListener("click", async () => {
            const bookmarkId = deleteSelect.value;

            if (!bookmarkId) {
                deleteStatus.textContent = "Please select a bookmark to delete.";
                return;
            }

            const selectedText =
                deleteSelect.options[deleteSelect.selectedIndex].text;

            if (!window.confirm(`Are you sure you want to delete "${selectedText}"?`)) {
                return;
            }

            deleteButton.disabled = true;
            deleteStatus.textContent = "Deleting bookmark…";

            try {
                if (!deleteBookmarkUrlTemplate) {
                    throw new Error("Delete bookmark URL is missing.");
                }

                const deleteUrl = deleteBookmarkUrlTemplate.replace(
                    "/0/delete/",
                    `/${bookmarkId}/delete/`
                );

                const response = await fetch(deleteUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "X-CSRFToken": getCsrfToken()
                    }
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || "Could not delete bookmark.");
                }

                deleteStatus.textContent = "Bookmark deleted.";

                // Refresh both selectors from the database.
                window.location.reload();
            } catch (error) {
                deleteStatus.textContent = error.message;
            } finally {
                deleteButton.disabled = false;
            }
        });

        // Start at page 1.
        showPage(1);
    })();



});

(() => {
    const form = document.getElementById("note-form");
    const editor = document.getElementById("note-editor");
    const list = document.getElementById("notes-list");
    const status = document.getElementById("note-status");

    if (!form || !editor || !list || !status) return;

    const titleInput = document.getElementById("note-title");
    const textInput = document.getElementById("note-text");
    const idInput = document.getElementById("note-id");

    function resetForm() {
        form.reset();
        idInput.value = "";
        document.getElementById("note-form-heading").textContent =
            "Create Note";
        status.textContent = "";
    }

    document.getElementById("add-note-btn").addEventListener("click", () => {
        resetForm();
        editor.hidden = false;
        titleInput.focus();
    });

    document.getElementById("cancel-note-btn").addEventListener("click", () => {
        editor.hidden = true;
        resetForm();
    });

    list.addEventListener("click", event => {
        const button = event.target.closest(".edit-note-btn");
        if (!button) return;

        const article = button.closest("[data-note-id]");
        idInput.value = article.dataset.noteId;
        titleInput.value = article.querySelector(".note-title").textContent;
        textInput.value = article.querySelector(".note-text").textContent;

        document.getElementById("note-form-heading").textContent =
            "Edit Note";

        editor.hidden = false;
        titleInput.focus();
    });

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const saveButton = form.querySelector('[type="submit"]');
        saveButton.disabled = true;
        status.textContent = "Saving note...";

        try {
            const response = await fetch(form.dataset.saveUrl, {
                method: "POST",
                body: new FormData(form),
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Unable to save note.");
            }

            const note = data.note;
            let article = list.querySelector(
                `[data-note-id="${note.id}"]`
            );

            if (!article) {
                article = document.createElement("article");
                article.className = "card mb-3";
                article.dataset.noteId = note.id;
                article.innerHTML = `
                            <div class="card-body">
                                <h3 class="h5 note-title"></h3>

                                <div class="note-text"
                                    style="white-space: pre-wrap;"></div>

                                <button type="button"
                                        class="btn btn-outline-primary btn-sm mt-3 edit-note-btn">
                                    Edit
                                </button>

                                <button type="button"
                                        class="btn btn-outline-danger btn-sm mt-3 delete-note-btn">
                                    Delete
                                </button>
                            </div>
                        `;

                const deleteUrlTemplate =
                    "{% url 'reader:delete_note_ajax' document.pk 999999 %}";

                article.querySelector(".delete-note-btn").dataset.deleteUrl =
                    deleteUrlTemplate.replace("999999", note.id);
                list.prepend(article);
            }

            article.querySelector(".note-title").textContent = note.title;
            article.querySelector(".note-text").textContent = note.text;

            const emptyMessage = document.getElementById("no-notes-message");
            if (emptyMessage) emptyMessage.remove();

            editor.hidden = true;
            resetForm();
        } catch (error) {
            status.textContent = error.message;
        } finally {
            saveButton.disabled = false;
        }
    });




    list.addEventListener("click", async event => {
        const button = event.target.closest(".delete-note-btn");
        if (!button) return;

        if (!confirm("Delete this note?")) return;

        button.disabled = true;

        try {
            const csrfToken = form.querySelector(
                '[name="csrfmiddlewaretoken"]'
            ).value;

            const response = await fetch(button.dataset.deleteUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                },
                mode: "same-origin"
            });

            const contentType =
                response.headers.get("content-type") || "";

            if (!response.ok) {
                throw new Error(`Delete failed (HTTP ${response.status}).`);
            }

            if (!contentType.includes("application/json")) {
                const responseText = await response.text();

                console.error("Unexpected delete response:", {
                    status: response.status,
                    url: response.url,
                    response: responseText.slice(0, 500)
                });

                throw new Error(
                    "The server returned HTML instead of JSON. Check the Network tab."
                );
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error("The server could not delete the note.");
            }

            // Remove the card only after the server confirms deletion.
            button.closest("[data-note-id]").remove();

            if (!list.querySelector("[data-note-id]")) {
                const emptyMessage = document.createElement("p");
                emptyMessage.id = "no-notes-message";
                emptyMessage.textContent = "No notes yet.";
                list.appendChild(emptyMessage);
            }

        } catch (error) {
            console.error("Delete note error:", error);
            alert(error.message);
        } finally {
            // The button may have been removed after a successful request.
            if (button.isConnected) {
                button.disabled = false;
            }
        }
    });

})();



(() => {
    const form = document.getElementById("ai-form");
    const list = document.getElementById("notes-list");
    const status = document.getElementById("ai-status");
    const questionInput = document.getElementById("ai-question");
    const askButton = document.getElementById("ask-ai-btn");

    if (!form || !list || !status || !questionInput || !askButton) {
        return;
    }

    function addNoteToList(note) {
        let article = list.querySelector(
            `[data-note-id="${note.id}"]`
        );

        if (!article) {
            article = document.createElement("article");
            article.className = "card mb-3";
            article.dataset.noteId = note.id;

            article.innerHTML = `
                <div class="card-body">
                    <h3 class="h5 note-title"></h3>
                    <div class="note-text"
                         style="white-space: pre-wrap;"></div>

                    <button type="button"
                            class="btn btn-outline-primary btn-sm mt-3 edit-note-btn">
                        Edit
                    </button>

                    <button type="button"
                            class="btn btn-outline-danger btn-sm mt-3 delete-note-btn">
                        Delete
                    </button>
                </div>
            `;

            const deleteUrlTemplate =
                "{% url 'reader:delete_note_ajax' document.pk 999999 %}";

            article.querySelector(".delete-note-btn").dataset.deleteUrl =
                deleteUrlTemplate.replace("999999", note.id);

            list.prepend(article);
        }

        article.querySelector(".note-title").textContent = note.title;
        article.querySelector(".note-text").textContent = note.text;

        const emptyMessage = document.getElementById("no-notes-message");
        if (emptyMessage) emptyMessage.remove();
    }

    form.addEventListener("submit", async event => {
        event.preventDefault();

        askButton.disabled = true;
        status.textContent = "Generating your answer...";

        try {
            const response = await fetch(form.dataset.aiUrl, {
                method: "POST",
                body: new FormData(form),
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json"
                },
                mode: "same-origin"
            });

            const contentType =
                response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error(
                    "The server returned an unexpected response. Check the Network tab."
                );
            }

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || "Unable to generate an answer.");
            }

            addNoteToList(data.note);

            questionInput.value = "";
            status.textContent = "Answer generated and saved to Notes.";
        } catch (error) {
            status.textContent = error.message;
        } finally {
            askButton.disabled = false;
        }
    });
})();





