(function () {
  "use strict";

  var hero = document.getElementById("hero");
  var particlesLayer = document.getElementById("heroParticles");
  var scrollCue = document.getElementById("scrollCue");
  var checkbox = document.getElementById("agree-checkbox");
  var ticketButton = document.getElementById("ticket-button");
  var rulesLink = document.getElementById("rules-link");
  var rulesModal = document.getElementById("rules-modal");
  var rulesClose = document.getElementById("rules-close");
  var rulesOverlay = document.getElementById("rules-overlay");

  var prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  /* ---------------- gate opening ---------------- */

  function openGate() {
    hero.classList.add("is-open");
  }

  if (prefersReducedMotion) {
    openGate();
  } else {
    window.addEventListener("load", function () {
      setTimeout(openGate, 700);
    });
    setTimeout(openGate, 2500);
  }

  if (scrollCue) {
    scrollCue.addEventListener("click", function () {
      var target = document.getElementById("invitation");
      if (target) target.scrollIntoView({ behavior: "smooth" });
    });
  }

  /* ---------------- particles: sparkles + fireflies ---------------- */

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function spawnParticles() {
    if (prefersReducedMotion || !particlesLayer) return;

    var sparkCount = window.innerWidth < 560 ? 14 : 24;
    var fireflyCount = window.innerWidth < 560 ? 6 : 10;

    for (var i = 0; i < sparkCount; i++) {
      var s = document.createElement("span");
      s.className = "spark";
      var size = rand(2, 5);
      s.style.left = rand(2, 98) + "vw";
      s.style.top = rand(4, 96) + "%";
      s.style.width = size + "px";
      s.style.height = size + "px";
      s.style.setProperty("--dur", rand(2.6, 5.5).toFixed(2) + "s");
      s.style.setProperty("--delay", rand(0, 6).toFixed(2) + "s");
      s.style.setProperty("--peak", rand(0.5, 0.95).toFixed(2));
      particlesLayer.appendChild(s);
    }

    for (var j = 0; j < fireflyCount; j++) {
      var f = document.createElement("span");
      f.className = "firefly";
      var fsize = rand(4, 7);
      f.style.left = rand(6, 94) + "vw";
      f.style.top = rand(40, 92) + "%";
      f.style.width = fsize + "px";
      f.style.height = fsize + "px";
      f.style.setProperty("--dur", rand(9, 16).toFixed(2) + "s");
      f.style.setProperty("--delay", rand(0, 10).toFixed(2) + "s");
      f.style.setProperty("--dx", rand(-40, 40).toFixed(0) + "px");
      f.style.setProperty("--rise", rand(140, 320).toFixed(0) + "px");
      particlesLayer.appendChild(f);
    }
  }

  spawnParticles();

  /* ---------------- scroll reveal ---------------- */

  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !prefersReducedMotion) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" }
    );
    revealEls.forEach(function (el) {
      revealObserver.observe(el);
    });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add("is-visible");
    });
  }

  /* ---------------- countdown ---------------- */

  // Mock start time — replace with the confirmed gate-opening time.
  var EVENT_DATE = new Date("2026-09-13T12:00:00+06:00");

  var cdDays = document.getElementById("cd-days");
  var cdHours = document.getElementById("cd-hours");
  var cdMins = document.getElementById("cd-mins");
  var cdSecs = document.getElementById("cd-secs");

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function updateCountdown() {
    if (!cdDays) return;
    var diff = EVENT_DATE.getTime() - Date.now();
    if (diff <= 0) {
      cdDays.textContent = "00";
      cdHours.textContent = "00";
      cdMins.textContent = "00";
      cdSecs.textContent = "00";
      return;
    }
    var totalSeconds = Math.floor(diff / 1000);
    var days = Math.floor(totalSeconds / 86400);
    var hours = Math.floor((totalSeconds % 86400) / 3600);
    var mins = Math.floor((totalSeconds % 3600) / 60);
    var secs = totalSeconds % 60;

    cdDays.textContent = pad(days);
    cdHours.textContent = pad(hours);
    cdMins.textContent = pad(mins);
    cdSecs.textContent = pad(secs);
  }

  if (cdDays) {
    updateCountdown();
    setInterval(updateCountdown, 1000);
  }

  /* ---------------- checkbox gates the ticket button ---------------- */

  function syncButtonState() {
    var agreed = checkbox && checkbox.checked;
    ticketButton.setAttribute("aria-disabled", agreed ? "false" : "true");
  }

  if (checkbox) {
    checkbox.addEventListener("change", syncButtonState);
    syncButtonState();
  }

  ticketButton.addEventListener("click", function (event) {
    if (ticketButton.getAttribute("aria-disabled") === "true") {
      event.preventDefault();
      if (checkbox) checkbox.focus();
    }
  });

  /* ---------------- rules modal ---------------- */

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
