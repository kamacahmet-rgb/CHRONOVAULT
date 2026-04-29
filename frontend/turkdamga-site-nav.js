/**
 * Ortak site üst çubuğu — TR/EN (yalnızca .cv-site-nav içi data-tr / data-en).
 */
function cvSetLang(lang, btn) {
  if (btn && btn.classList) {
    document.querySelectorAll(".cv-site-nav .cv-lang-btn").forEach(function (b) {
      var on = b === btn;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  var attr = lang === "en" ? "data-en" : "data-tr";
  document
    .querySelectorAll(".cv-site-nav [data-tr][data-en], .header-page-title[data-tr][data-en]")
    .forEach(function (el) {
      var v = el.getAttribute(attr);
      if (v != null && v !== "") el.textContent = v;
    });
}
