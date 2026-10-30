
document.addEventListener("DOMContentLoaded", () => {
    const pages = [
        ...document.querySelectorAll("#reader-pages .reader-page"),
    ];

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

    const previousButton = document.getElementById("previous-page");
    const nextButton = document.getElementById("next-page");
    const pageInput = document.getElementById("page-number-input");
    const pageStatus = document.getElementById("page-navigation-status");

    if (
        !pages.length ||
        !audio ||
        !audio.dataset.ttsUrl ||
        !playButton ||
        !pauseButton ||
        !stopButton ||
        !backButton ||
        !forwardButton ||
        !speedSelect ||
        !languageSelect ||
        !voiceSelect
    ) {
        if (status) {
            status.textContent = "The reader could not be initialized.";
        }
        return;
    }

    const MAX_CHUNK_LENGTH = 9000;
    const PREFETCH_SECONDS = 8;
    const chunks = [];
    const audioCache = new Map();

    // Read textarea.value so unsaved edits are included.
    pages.forEach((page, pageIndex) => {
        const textarea = page.querySelector(".reader-page-text");
        const text = textarea?.value.trim() || "";
        const paragraphs = text
            .split(/\n+/)
            .map(part => part.trim())
            .filter(Boolean);

        let buffer = "";

        function addChunk(value) {
            chunks.push({
                text: value,
                pageIndex,
                pageNumber: page.dataset.pageNumber,
            });
        }

        paragraphs.forEach(paragraph => {
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

    function updateStatus(message) {
        if (status) status.textContent = message;
    }

    function releaseCurrentUrl() {
        if (currentAudioUrl) {
            URL.revokeObjectURL(currentAudioUrl);
            currentAudioUrl = null;
        }
    }

    function showPage(index) {
        if (index < 0 || index >= pages.length) return;

        pages.forEach((page, i) => {
            page.hidden = i !== index;
        });

        if (pageInput) pageInput.value = index + 1;

        if (pageStatus) {
            pageStatus.textContent =
                `Page ${index + 1} of ${pages.length}`;
        }

        if (previousButton) previousButton.disabled = index === 0;
        if (nextButton) nextButton.disabled = index === pages.length - 1;
    }

    function cancelPlayback() {
        requestVersion++;
        isLoading = false;
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        releaseCurrentUrl();
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
                    // Keep the default error message.
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
        if (currentIndex + 1 < chunks.length) {
            requestAudio(currentIndex + 1).catch(() => {});
        }
    }

    async function playChunk(index = currentIndex) {
        if (index < 0 || index >= chunks.length) {
            updateStatus(
                chunks.length
                    ? "Finished reading the document."
                    : "There is no text to read."
            );
            return;
        }

        currentIndex = index;
        const version = ++requestVersion;
        isLoading = true;

        audio.pause();
        audio.removeAttribute("src");
        audio.load();
        releaseCurrentUrl();

        const chunk = chunks[currentIndex];
        showPage(chunk.pageIndex);

        updateStatus(`Preparing page ${chunk.pageNumber}...`);

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

            prefetchNext();
        } catch (error) {
            if (version !== requestVersion) return;

            isLoading = false;
            updateStatus(error.message || "Unable to play audio.");
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

        if (
            Number.isFinite(audio.duration) &&
            audio.currentTime + 10 >= audio.duration
        ) {
            if (currentIndex < chunks.length - 1) {
                playChunk(currentIndex + 1);
            } else {
                audio.currentTime = Math.max(0, audio.duration - 0.1);
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
        audioCache.clear();

        if (!audio.paused || isLoading) {
            playChunk(currentIndex);
        } else {
            updateStatus("Voice settings changed. Press Play to continue.");
        }
    }

    languageSelect.addEventListener("change", changeVoiceSetting);
    voiceSelect.addEventListener("change", changeVoiceSetting);

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

    // Keep page navigation within the real page range.
    function navigateToInputPage() {
        if (!pageInput) return;

        const value = pageInput.value.trim();
        const number = Number(value);

        if (
            value === "" ||
            !Number.isInteger(number) ||
            number < 1 ||
            number > pages.length
        ) {
            const visibleIndex = pages.findIndex(page => !page.hidden);
            pageInput.value = Math.max(visibleIndex + 1, 1);
            if (pageStatus) {
                pageStatus.textContent =
                    `Enter a whole page number from 1 to ${pages.length}.`;
            }
            return;
        }

        showPage(number - 1);
    }

    previousButton?.addEventListener("click", () => {
        const index = pages.findIndex(page => !page.hidden);
        showPage(index - 1);
    });

    nextButton?.addEventListener("click", () => {
        const index = pages.findIndex(page => !page.hidden);
        showPage(index + 1);
    });

    pageInput?.addEventListener("change", navigateToInputPage);

    pageInput?.addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            navigateToInputPage();
        }
    });

    showPage(0);
});
