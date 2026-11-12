(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- gate ----------------
     The opening itself is a CSS animation (works without JS). Here we
     only let a tap skip the wait, and remember the visit so the gate
     doesn't replay on every reload. */

  var gate = document.getElementById("gate");
  if (gate) {
    try { sessionStorage.setItem("gateSeen", "1"); } catch (e) {}
    gate.addEventListener("click", function () {
      if (gate.classList.contains("is-skipped")) return;
      // restart the animations with the short timings
      gate.classList.add("is-skipped");
      var leaves = gate.querySelectorAll(".gate__leaf, .gate__glow");
      for (var i = 0; i < leaves.length; i++) {
        var el = leaves[i];
        el.style.animation = "none";
        void el.offsetWidth;
        el.style.animation = "";
      }
      gate.style.animation = "none";
      void gate.offsetWidth;
      gate.style.animation = "gate-away .5s ease .55s forwards";
    });
  }

  /* ---------------- golden dust ---------------- */

  var canvas = document.getElementById("dust");
  if (canvas && !reduceMotion && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = 0, h = 0, motes = [], running = true, raf = null;

    function rand(a, b) { return Math.random() * (b - a) + a; }

    function mote(initial) {
      return {
        x: rand(0, w),
        y: initial ? rand(0, h) : h + 10,
        r: rand(0.5, 2.1),
        vy: rand(0.12, 0.45),
        vx: rand(-0.12, 0.12),
        phase: rand(0, Math.PI * 2),
        tw: rand(0.008, 0.025),
        a: rand(0.25, 0.85),
      };
    }

    function resize() {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var count = w < 600 ? 45 : 85;
      motes = [];
      for (var i = 0; i < count; i++) motes.push(mote(true));
    }

    function frame() {
      ctx.clearRect(0, 0, w, h);
      for (var i = 0; i < motes.length; i++) {
        var m = motes[i];
        m.y -= m.vy;
        m.x += m.vx + Math.sin(m.phase) * 0.15;
        m.phase += m.tw;
        if (m.y < -10) motes[i] = m = mote(false);
        var alpha = m.a * (0.55 + 0.45 * Math.sin(m.phase * 2));
        var g = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, m.r * 3.2);
        g.addColorStop(0, "rgba(255,232,180," + alpha + ")");
        g.addColorStop(1, "rgba(198,160,106,0)");
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.r * 3.2, 0, Math.PI * 2);
        ctx.fill();
      }
      if (running) raf = requestAnimationFrame(frame);
    }

    resize();
    frame();
    window.addEventListener("resize", resize);

    // pause when the hero is off-screen
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        var visible = entries[0].isIntersecting;
        if (visible && !running) { running = true; frame(); }
        else if (!visible) { running = false; cancelAnimationFrame(raf); }
      }).observe(canvas);
    }
  }

  /* ---------------- reveal on scroll ---------------- */

  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }
    );
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* ---------------- pinned buy bar (mobile) ----------------
     Shown once the hero's buy button has scrolled away, hidden again
     while the final buy button is on screen (no point doubling it). */

  var bar = document.getElementById("buybar");
  var heroBuy = document.getElementById("heroBuy");
  var finalBuy = document.getElementById("finalBuy");
  if (bar && heroBuy && "IntersectionObserver" in window) {
    var heroGone = false, finalShown = false;
    function sync() {
      var show = heroGone && !finalShown;
      bar.classList.toggle("is-visible", show);
      document.body.classList.toggle("has-buybar", show);
    }
    new IntersectionObserver(function (e) {
      heroGone = !e[0].isIntersecting && e[0].boundingClientRect.top < 0;
      sync();
    }).observe(heroBuy);
    if (finalBuy) {
      new IntersectionObserver(function (e) {
        finalShown = e[0].isIntersecting;
        sync();
      }).observe(finalBuy);
    }
  }
})();
