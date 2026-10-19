/* De installatielink (/installeren/, zie config/pwa.py en
   templates/installeren.html): zet het blok aan dat bij dit toestel hoort.
   Android/Chrome geeft de installatie aan ons door (beforeinstallprompt) en
   krijgt dan één knop; komt dat signaal niet (Samsung Internet, Firefox),
   dan blijft de uitleg via het menu staan. De iPhone krijgt de stappen via
   het Deel-menu, een computer de QR-code.
   Zet iemand deze pagina zelf op het beginscherm en opent de app hier, dan
   meteen door naar de startpagina: het icoon hoort de app te openen, niet
   deze uitleg. */
(function () {
  var uitgesteld = null;
  var standalone = window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;
  // iPadOS doet zich voor als Mac; de aanraakpunten verraden hem.
  var iOS = /iPhone|iPad|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  var android = /Android/.test(navigator.userAgent);
  if (standalone) {
    location.replace("/");
    return;
  }
  var toestel = standalone ? "klaar" : iOS ? "ios" : android ? "android" : "computer";

  function blokken() { return document.querySelectorAll(".installatie[data-toestel]"); }
  function toon(soort) {
    blokken().forEach(function (el) {
      el.hidden = el.getAttribute("data-toestel") !== soort;
    });
  }
  function androidKnop(aan) {
    document.querySelectorAll("[data-android]").forEach(function (el) {
      el.hidden = (el.getAttribute("data-android") === "knop") !== aan;
    });
  }

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    uitgesteld = event;
    if (toestel === "android") androidKnop(true);
  });
  window.addEventListener("appinstalled", function () { toon("klaar"); });

  toon(toestel);
  var knop = document.querySelector("[data-actie=installeren]");
  if (knop) knop.addEventListener("click", function () {
    if (!uitgesteld) return;
    uitgesteld.prompt();
    uitgesteld.userChoice.then(function (keuze) {
      uitgesteld = null;
      if (keuze.outcome === "accepted") toon("klaar");
      else androidKnop(false);
    });
  });
})();
