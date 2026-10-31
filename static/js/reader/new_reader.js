const fileInput = document.getElementById("pdf-file");
const dropZone = document.getElementById("drop-zone");
const fileLabel = document.getElementById("file-label");

fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
        fileLabel.textContent = "Selected: " + fileInput.files[0].name;
    }
});

dropZone.addEventListener("dragover", event => {
    event.preventDefault();
    dropZone.classList.add("bg-light");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("bg-light");
});

dropZone.addEventListener("drop", event => {
    event.preventDefault();
    dropZone.classList.remove("bg-light");

    const files = event.dataTransfer.files;
    if (files.length) {
        fileInput.files = files;
        fileInput.dispatchEvent(new Event("change"));
    }
});