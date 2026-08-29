(function () {
  "use strict";

  var btn = document.getElementById("whatsapp-fab");
  var panel = document.getElementById("whatsapp-panel");
  if (!btn || !panel) return;

  function setOpen(open) {
    panel.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  btn.addEventListener("click", function (event) {
    event.stopPropagation();
    setOpen(!panel.classList.contains("is-open"));
  });

  document.addEventListener("click", function (event) {
    if (!panel.contains(event.target) && event.target !== btn) {
      setOpen(false);
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") setOpen(false);
  });
})();
