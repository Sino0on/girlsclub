(function () {
  "use strict";

  var video = document.getElementById("scanner-video");
  var canvas = document.getElementById("scanner-canvas");
  var ctx = canvas.getContext("2d", { willReadFrequently: true });
  var statusEl = document.getElementById("scanner-status");
  var resultEl = document.getElementById("scanner-result");
  var resultTitle = document.getElementById("scanner-result-title");
  var resultSubtitle = document.getElementById("scanner-result-subtitle");
  var iconOk = document.getElementById("scanner-result-icon-ok");
  var iconError = document.getElementById("scanner-result-icon-error");
  var spinner = document.getElementById("scanner-result-spinner");
  var errorEl = document.getElementById("scanner-error");
  var errorDetailEl = document.getElementById("scanner-error-detail");
  var retryBtn = document.getElementById("scanner-retry");
  var manualToggle = document.getElementById("scanner-manual-toggle");
  var manualForm = document.getElementById("scanner-manual-form");
  var manualInput = document.getElementById("scanner-manual-input");
  var csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  var csrfToken = csrfInput ? csrfInput.value : "";

  var TOKEN_RE = /([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/;
  var COOLDOWN_MS = 4000;
  var RESULT_DISPLAY_MS = 2200;

  var scanning = true;
  var lastCode = null;
  var lastCodeAt = 0;
  var rafId = null;

  function extractToken(text) {
    var match = text.match(TOKEN_RE);
    return match ? match[1] : null;
  }

  var REASON_TITLES = {
    busy: "Проверяем…",
    ok: "Билет действителен",
    used: "Уже использован",
    rejected: "Билет аннулирован",
    not_issued: "Билет не оформлен",
    not_found: "Билет не найден",
    error: "Ошибка связи",
  };

  function showResult(state, reason, subtitle) {
    statusEl.hidden = true;
    resultEl.className = "scanner__result scanner__result--" + state + " is-visible";
    var title = REASON_TITLES[reason] || reason;
    resultTitle.textContent = title;
    // Don't repeat the subtitle if it's just the same phrase as the title
    resultSubtitle.textContent = subtitle && subtitle !== title ? subtitle : "";

    // Toggle via style.display, not the `hidden` property — SVG elements
    // don't reliably reflect `.hidden` to the content attribute in every
    // browser, which left both icons visible at once.
    spinner.style.display = state === "busy" ? "block" : "none";
    iconOk.style.display = state === "ok" ? "block" : "none";
    iconError.style.display = state === "error" ? "block" : "none";
  }

  function hideResult() {
    resultEl.classList.remove("is-visible");
    statusEl.hidden = false;
  }

  function vibrate(pattern) {
    if (navigator.vibrate) {
      try {
        navigator.vibrate(pattern);
      } catch (e) {
        /* ignore */
      }
    }
  }

  function beep(freq, duration) {
    try {
      var AudioCtx = window.AudioContext || window.webkitAudioContext;
      var actx = new AudioCtx();
      var osc = actx.createOscillator();
      var gain = actx.createGain();
      osc.connect(gain);
      gain.connect(actx.destination);
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.15, actx.currentTime);
      osc.start();
      osc.stop(actx.currentTime + duration / 1000);
      osc.onended = function () {
        actx.close();
      };
    } catch (e) {
      /* Web Audio unavailable — silently skip, visuals still work */
    }
  }

  function submitToken(token) {
    scanning = false;
    showResult("busy", "busy", "");

    fetch("/tickets/scan/" + token + "/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.ok) {
          showResult("ok", "ok", data.full_name + " · билетов: " + data.quantity);
          vibrate(120);
          beep(880, 150);
        } else {
          showResult("error", data.reason, data.message);
          vibrate([80, 60, 80]);
          beep(220, 250);
        }
      })
      .catch(function () {
        showResult("error", "error", "Проверьте подключение к интернету");
      })
      .finally(function () {
        setTimeout(function () {
          hideResult();
          scanning = true;
        }, RESULT_DISPLAY_MS);
      });
  }

  function tick() {
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      var imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      var code = window.jsQR(imageData.data, imageData.width, imageData.height, {
        inversionAttempts: "dontInvert",
      });

      if (code && code.data && scanning) {
        var now = Date.now();
        if (code.data !== lastCode || now - lastCodeAt > COOLDOWN_MS) {
          lastCode = code.data;
          lastCodeAt = now;
          var token = extractToken(code.data);
          if (token) submitToken(token);
        }
      }
    }
    rafId = requestAnimationFrame(tick);
  }

  function showCameraError(detail) {
    errorDetailEl.textContent = detail;
    errorEl.style.display = "flex";
  }

  // Names getUserMedia actually throws — show the real reason instead of
  // a generic "didn't work", so this is diagnosable from the phone alone.
  var GET_USER_MEDIA_ERRORS = {
    NotAllowedError: "Доступ к камере запрещён. Откройте настройки сайта в браузере и разрешите камеру, затем нажмите «Повторить».",
    PermissionDeniedError: "Доступ к камере запрещён. Откройте настройки сайта в браузере и разрешите камеру, затем нажмите «Повторить».",
    NotFoundError: "На этом устройстве не найдена подходящая камера.",
    NotSupportedError: "На этом устройстве не найдена подходящая камера.",
    NotReadableError: "Камера занята другим приложением. Закройте его и нажмите «Повторить».",
    OverconstrainedError: "Не удалось выбрать заднюю камеру устройства.",
    SecurityError: "Браузер заблокировал доступ к камере на этой странице.",
  };

  var currentStream = null;
  var starting = false;

  function stopCurrentStream() {
    if (currentStream) {
      currentStream.getTracks().forEach(function (track) {
        track.stop();
      });
      currentStream = null;
    }
  }

  function startCamera() {
    // Ignore overlapping calls (e.g. a stray extra tap on "Повторить"
    // while a request is already in flight) — those used to race with
    // an already-working stream and leave a stale error screen sitting
    // on top of a camera feed that was actually fine underneath it.
    if (starting) return;
    starting = true;
    errorEl.style.display = "none";

    if (!window.isSecureContext) {
      starting = false;
      showCameraError(
        "Страница открыта не по HTTPS (" + location.protocol + "//" + location.host +
        "). Браузеры разрешают камеру только на защищённых (https://) страницах — " +
        "откройте сайт по https:// и попробуйте снова."
      );
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      starting = false;
      showCameraError("Этот браузер не поддерживает доступ к камере со страницы. Попробуйте актуальный Chrome или Safari.");
      return;
    }

    stopCurrentStream();

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } } })
      .then(function (stream) {
        currentStream = stream;
        video.srcObject = stream;
        // A success here always wins, even over a stale error left by
        // some earlier/overlapping failed attempt.
        errorEl.style.display = "none";
        return video.play();
      })
      .then(function () {
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(tick);
      })
      .catch(function (err) {
        var detail = GET_USER_MEDIA_ERRORS[err && err.name];
        showCameraError(detail || ("Причина: " + ((err && (err.name || err.message)) || "неизвестна") + "."));
      })
      .finally(function () {
        starting = false;
      });
  }

  retryBtn.addEventListener("click", startCamera);

  function isManualFormOpen() {
    return manualForm.style.display === "flex";
  }

  manualToggle.addEventListener("click", function () {
    var open = !isManualFormOpen();
    manualForm.style.display = open ? "flex" : "none";
    if (open) manualInput.focus();
  });

  manualForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var raw = manualInput.value.trim();
    var token = extractToken(raw) || raw;
    if (token) submitToken(token);
    manualInput.value = "";
    manualForm.style.display = "none";
  });

  startCamera();
})();
