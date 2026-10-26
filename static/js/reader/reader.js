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

        pages.forEach((page, index) => {
            page.hidden = index !== chunk.pageIndex;
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

        if (audio.src && audio.paused && audio.currentTime > 0) {
            try {
                await audio.play();
                updateStatus("Reading resumed.");
            } catch {
                updateStatus("Unable to resume playback.");
            }
            return;
        }

        await playChunk(currentIndex);
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

        pageInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                clearTimeout(pageInputTimer);

                const pageNumber = Number(pageInput.value);
                if (showPage(pageNumber)) {
                    pageInput.blur();
                }
            }
        });

        pageInput.addEventListener("input", () => {
            clearTimeout(pageInputTimer);

            pageInputTimer = setTimeout(() => {
                if (pageInput.value.trim() === "") return;

                const pageNumber = Number(pageInput.value);
                if (Number.isInteger(pageNumber)) {
                    showPage(pageNumber);
                }
            }, 700);
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

                // const deleteUrl = deleteBookmarkUrlTemplate.replace(
                //     /0\/?$/,
                //     `${bookmarkId}/`
                // );

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






