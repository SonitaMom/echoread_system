const FALLBACK = "en";
let dict = {};

function getLang() {
  return localStorage.getItem("lang") || FALLBACK;
}

async function loadDict(lang) {
  if (lang === FALLBACK) return {};

  const page = document.body.dataset.page;
  const files = ["common"];
  if (page) files.push(page);

  const parts = await Promise.all(
    files.map(async (name) => {
      const res = await fetch(`${window.LANG_URL}${lang}/${name}.json`);
      if (!res.ok) {
        console.warn(`Missing ${lang}/${name}.json (${res.status})`);
        return {};
      }

      return res.json();
    }),
  );

  return Object.assign({}, ...parts);
}
// load the json file

// async function loadDict(lang){
//     const res = await fetch(`${window.LANG_URL}${lang}.json`);
//     return res.json();
// }

// // look up key
function t(path) {
  return path.split(".").reduce((o, k) => (o ? o[k] : undefined), dict);
}

// change function
async function setLanguage(lang) {
  try {
    dict = await loadDict(lang);
  } catch (err) {
    console.error(err);
    lang = FALLBACK;
    dict = {};
  }

  localStorage.setItem("lang", lang);
  document.documentElement.lang = lang;
  // dict = await loadDict(lang);

  // replace text for every tag
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (el.dataset.en === undefined) el.dataset.en = el.textContent;
    el.textContent = t(el.dataset.i18n) ?? el.dataset.en;
  });

  // for attribute
  document.querySelectorAll("[data-i18n-attr]").forEach((el) => {
    const [attr, key] = el.dataset.i18nAttr.split(":");
    if (el.dataset["en_" + attr] === undefined) {
      el.dataset["en_" + attr] = el.getAttribute(attr);
    }
    el.setAttribute(attr, t(key) ?? el.dataset["en_" + attr]);
  });

  document.querySelectorAll("[data-i18n]").forEach(el => {
    const isHtml = el.hasAttribute("data-i18n-html");
    if (el.dataset.en === undefined) el.dataset.en = isHtml ? el.innerHTML : el.textContent;
    const value = t(el.dataset.i18n) ?? el.dataset.en;
    if (isHtml) el.innerHTML = value; else el.textContent = value;
});

  // move the switch and highlight the active label
  const toggle = document.getElementById("langToggle");
  toggle.classList.toggle("on", lang === "km");
  toggle.setAttribute("aria-checked", lang === "km");
  document.getElementById("labelEn").classList.toggle("active", lang === "en");
  document.getElementById("labelKm").classList.toggle("active", lang === "km");

  // tell screen reader users
  document.getElementById("langAnnounce").textContent =
    lang === "km" ? "ភាសាខ្មែរ" : "English";
}

// When the page load
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("langToggle");

  // clicking the switch flips the language
  toggle.addEventListener("click", () => {
    setLanguage(getLang() === "km" ? "en" : "km");
  });

  // apply the save language
  setLanguage(getLang());
});

// TEMPORARY: toggle test only (no JSON needed)

// function getLang() {
//     return localStorage.getItem("lang") || "en";
// }

// function updateSwitch(lang) {
//     const toggle = document.getElementById("langToggle");
//     toggle.classList.toggle("on", lang === "km");
//     toggle.setAttribute("aria-checked", lang === "km");
//     document.getElementById("labelEn").classList.toggle("active", lang === "en");
//     document.getElementById("labelKm").classList.toggle("active", lang === "km");
//     document.documentElement.lang = lang;
//     document.getElementById("langAnnounce").textContent =
//         lang === "km" ? "ភាសាខ្មែរ" : "English";
//     console.log("Language is now:", lang);
// }

// document.addEventListener("DOMContentLoaded", () => {
//     const toggle = document.getElementById("langToggle");

//     toggle.addEventListener("click", () => {
//         const next = getLang() === "km" ? "en" : "km";
//         localStorage.setItem("lang", next);
//         updateSwitch(next);
//     });

//     updateSwitch(getLang());
// });
