(function () {
  "use strict";

  var rulesLink = document.getElementById("rules-link");
  var rulesModal = document.getElementById("rules-modal");
  var rulesClose = document.getElementById("rules-close");
  var rulesOverlay = document.getElementById("rules-overlay");

  var lastFocused = null;

  function openRules() {
    lastFocused = document.activeElement;
    rulesModal.classList.add("is-visible");
    rulesModal.setAttribute("aria-hidden", "false");
    rulesClose.focus();
    document.addEventListener("keydown", onRulesKeydown);
  }

  function closeRules() {
    rulesModal.classList.remove("is-visible");
    rulesModal.setAttribute("aria-hidden", "true");
    document.removeEventListener("keydown", onRulesKeydown);
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  function onRulesKeydown(event) {
    if (event.key === "Escape") closeRules();
  }

  if (rulesLink) rulesLink.addEventListener("click", openRules);
  if (rulesClose) rulesClose.addEventListener("click", closeRules);
  if (rulesOverlay) rulesOverlay.addEventListener("click", closeRules);
})();
