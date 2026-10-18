/* De klusapp als app op het beginscherm (PWA) — zie config/pwa.py en
   development/PWA.md.
   Op elk scherm: de service worker registreren.
   Alleen op het startscherm (waar #installeer staat): de installatie
   aanbieden. Android/Chrome geeft daar een eigen venster voor
   (beforeinstallprompt); Safari op de iPhone niet, daar staat dan een korte
   uitleg. Wie het balkje wegtikt, ziet het op dit toestel niet meer terug. */
(function () {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }

  var SLEUTEL = "installeer-weggetikt";
  var uitgesteld = null;
  var standalone = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  // iPadOS doet zich voor als Mac; de aanraakpunten verraden hem.
  var iOS = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function weggetikt() {
    try { return localStorage.getItem(SLEUTEL) === "1"; } catch (e) { return false; }
  }
  function onthoud() {
    try { localStorage.setItem(SLEUTEL, "1"); } catch (e) {}
  }
  function balk() { return document.getElementById("installeer"); }

  function toon(soort) {
    var b = balk();
    if (!b || standalone || weggetikt()) return;
    b.querySelectorAll("[data-soort]").forEach(function (el) {
      el.hidden = el.getAttribute("data-soort") !== soort;
    });
    b.hidden = false;
  }
  function verberg() {
    var b = balk();
    if (b) b.hidden = true;
  }

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    uitgesteld = event;
    toon("android");
  });
  window.addEventListener("appinstalled", verberg);

  document.addEventListener("DOMContentLoaded", function () {
    var b = balk();
    if (!b) return;
    b.querySelector("[data-actie=installeren]").addEventListener("click", function () {
      if (!uitgesteld) return;
      uitgesteld.prompt();
      uitgesteld.userChoice.then(function () {
        uitgesteld = null;
        verberg();
      });
    });
    b.querySelector("[data-actie=weg]").addEventListener("click", function () {
      onthoud();
      verberg();
    });
    if (uitgesteld) toon("android");
    else if (iOS) toon("ios");
  });
})();
