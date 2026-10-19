/* TIJDELIJK / TEST: pushmeldingen (zie pushberichten/). Alleen geladen op
   develop (settings.TESTFUNCTIES), via basis.html.
   - Op het startscherm staat een knop "Meldingen aanzetten" (#testmelding).
     Op de iPhone werkt dat alleen in de app op het beginscherm, en iOS vraagt
     pas toestemming na een tik: daarom een knop en geen automatische vraag.
   - Op elk scherm: gaat de app naar de achtergrond, dan meldt hij zich
     "dicht" bij de server; komt hij terug, dan "open". De server stuurt een
     minuut na "dicht" een melding als er intussen geen "open" kwam. */
(function () {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return;

  var csrf = document.querySelector('meta[name="csrf-token"]');
  csrf = csrf ? csrf.getAttribute("content") : "";

  function abonnement() {
    return navigator.serviceWorker.ready.then(function (reg) {
      return reg.pushManager.getSubscription();
    });
  }

  function base64NaarBytes(tekst) {
    var opgevuld = (tekst + "===".slice((tekst.length + 3) % 4)).replace(/-/g, "+").replace(/_/g, "/");
    var ruw = atob(opgevuld);
    var bytes = new Uint8Array(ruw.length);
    for (var i = 0; i < ruw.length; i++) bytes[i] = ruw.charCodeAt(i);
    return bytes;
  }

  function aanzetten() {
    return Notification.requestPermission().then(function (keuze) {
      if (keuze !== "granted") throw new Error("geen toestemming");
      return fetch("/push/sleutel/", { credentials: "same-origin" });
    }).then(function (r) { return r.json(); }).then(function (data) {
      return navigator.serviceWorker.ready.then(function (reg) {
        return reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: base64NaarBytes(data.sleutel),
        });
      });
    }).then(function (abo) {
      return fetch("/push/aanmelden/", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(abo.toJSON()),
      });
    });
  }

  function meld(stand) {
    abonnement().then(function (abo) {
      if (!abo) return;
      var form = new FormData();
      form.append("csrfmiddlewaretoken", csrf);
      form.append("endpoint", abo.endpoint);
      form.append("stand", stand);
      navigator.sendBeacon("/push/status/", form);
    }).catch(function () {});
  }

  document.addEventListener("visibilitychange", function () {
    meld(document.visibilityState === "hidden" ? "dicht" : "open");
  });
  // pageshow: ook bij terugkomen uit de achtergrond-cache van de browser
  window.addEventListener("pageshow", function () { meld("open"); });

  document.addEventListener("DOMContentLoaded", function () {
    var blok = document.getElementById("testmelding");
    if (!blok) return;
    var knop = blok.querySelector("button");
    var uitleg = blok.querySelector(".installeer-tekst span");
    if (Notification.permission === "denied") return;
    abonnement().then(function (abo) {
      if (abo && Notification.permission === "granted") return;
      blok.hidden = false;
    }).catch(function () {});
    knop.addEventListener("click", function () {
      knop.disabled = true;
      aanzetten().then(function () {
        uitleg.textContent = "Aan! Sluit de app en wacht een minuut.";
        knop.hidden = true;
      }).catch(function () {
        uitleg.textContent = "Dat lukte niet. Op de iPhone werkt het alleen in de app op je beginscherm.";
        knop.disabled = false;
      });
    });
  });
})();
