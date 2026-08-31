(function () {
  "use strict";

  var video = document.getElementById("scanner-video");
  var canvas = document.getElementById("scanner-canvas");
  var ctx = canvas.getContext("2d", { willReadFrequently: true });
  var statusEl = document.getElementById("scanner-status");
  var statusText = document.getElementById("scanner-status-text");
  var errorEl = document.getElementById("scanner-error");
  var retryBtn = document.getElementById("scanner-retry");
  var manualToggle = document.getElementById("scanner-manual-toggle");
  var manualForm = document.getElementById("scanner-manual-form");
  var manualInput = document.getElementById("scanner-manual-input");
  var csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
  var csrfToken = csrfInput ? csrfInput.value : "";

  var TOKEN_RE = /([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/;
  var COOLDOWN_MS = 4000;
  var RESULT_DISPLAY_MS = 1800;

  var scanning = true;
  var lastCode = null;
  var lastCodeAt = 0;
  var rafId = null;

  function extractToken(text) {
    var match = text.match(TOKEN_RE);
    return match ? match[1] : null;
  }

  function setStatus(state, text) {
    statusEl.className = "scanner__status scanner__status--" + state;
    statusText.textContent = text;
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
    setStatus("busy", "Проверяем…");

    fetch("/tickets/scan/" + token + "/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.ok) {
          setStatus("ok", "✓ " + data.full_name + " · билетов: " + data.quantity);
          vibrate(120);
          beep(880, 150);
        } else {
          setStatus("error", "✕ " + data.message);
          vibrate([80, 60, 80]);
          beep(220, 250);
        }
      })
      .catch(function () {
        setStatus("error", "Не удалось связаться с сервером");
      })
      .finally(function () {
        setTimeout(function () {
          setStatus("idle", "Наведите камеру на QR-код билета");
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

  function startCamera() {
    errorEl.hidden = true;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } } })
      .then(function (stream) {
        video.srcObject = stream;
        video.play();
        if (rafId) cancelAnimationFrame(rafId);
        rafId = requestAnimationFrame(tick);
      })
      .catch(function () {
        errorEl.hidden = false;
      });
  }

  retryBtn.addEventListener("click", startCamera);

  manualToggle.addEventListener("click", function () {
    manualForm.hidden = !manualForm.hidden;
    if (!manualForm.hidden) manualInput.focus();
  });

  manualForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var raw = manualInput.value.trim();
    var token = extractToken(raw) || raw;
    if (token) submitToken(token);
    manualInput.value = "";
    manualForm.hidden = true;
  });

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    startCamera();
  } else {
    errorEl.hidden = false;
  }
})();
