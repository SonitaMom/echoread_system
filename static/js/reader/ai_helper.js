document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("ai-helper-btn");
    const status = document.getElementById("ai-helper-status");
    const editForm = document.getElementById("edit-reader-form");
    const pageContainer = document.getElementById("reader-pages");

    if (!button || !status || !editForm || !pageContainer) {
        return;
    }

    button.addEventListener("click", async () => {
        const textareas = [
            ...pageContainer.querySelectorAll(".reader-page-text"),
        ];

        if (!textareas.length) {
            status.textContent = "There are no pages to clean.";
            return;
        }

        // Capture all pages, including currently hidden pages.
        const pages = textareas.map((textarea) => {
            const section = textarea.closest(".reader-page");

            return {
                page_number: Number(section.dataset.pageNumber),
                text: textarea.value,
            };
        });

        if (pages.some((page) => !Number.isInteger(page.page_number))) {
            status.textContent = "Could not identify all page numbers.";
            return;
        }

        const csrfInput = editForm.querySelector(
            'input[name="csrfmiddlewaretoken"]'
        );

        if (!csrfInput) {
            status.textContent = "Security token missing. Reload the page.";
            return;
        }

        button.disabled = true;
        status.textContent =
            "AI Helper is cleaning all pages. Please wait.";

        try {
            const response = await fetch(
                button.dataset.url,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfInput.value,
                    },
                    mode: "same-origin",
                    body: JSON.stringify({ pages }),
                }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "AI Helper could not process the text."
                );
            }

            if (!Array.isArray(data.pages) ||
                data.pages.length !== textareas.length) {
                throw new Error("AI Helper returned an incomplete page list.");
            }

            // Validate the complete response before changing any textarea.
            const originalNumbers = new Set(
                pages.map((page) => page.page_number)
            );
            const cleanedMap = new Map();

            for (const page of data.pages) {
                if (
                    !page ||
                    !Number.isInteger(page.page_number) ||
                    !originalNumbers.has(page.page_number) ||
                    cleanedMap.has(page.page_number) ||
                    typeof page.text !== "string"
                ) {
                    throw new Error("AI Helper returned invalid page data.");
                }

                cleanedMap.set(page.page_number, page.text);
            }

            if (cleanedMap.size !== textareas.length) {
                throw new Error("AI Helper missed one or more pages.");
            }

            // Update the editor only after every page has passed validation.
            for (const textarea of textareas) {
                const section = textarea.closest(".reader-page");
                const pageNumber = Number(section.dataset.pageNumber);

                textarea.value = cleanedMap.get(pageNumber);
            }

            status.textContent =
                "Formatting cleaned for all pages. Review the text, then Save changes to keep it.";
        } catch (error) {
            status.textContent =
                error.message || "AI Helper failed. Your text was not saved.";
        } finally {
            button.disabled = false;
        }
    });
});





