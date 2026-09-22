/* Live zoeken op het klussenscherm: zelfde aanpak als static/js/fotozoeken.js
   voor de foto tab — bij elke toetsaanslag (met een korte pauze erin) en bij
   het kiezen van een klus haalt dit script dezelfde pagina opnieuw op en
   vervangt alleen de klussenlijst.

   Bewust géén los JSON/fragment-endpoint: dit haalt gewoon de normale
   klussen-pagina op en pakt er client-side het lijstdeel uit. Zonder JS (of
   zonder verbinding) werkt het gewone <form method=get> gewoon nog steeds.

   De zoekbare klus-kiezer zelf (knop + popover) zit in static/js/kluskiezer.js,
   gedeeld met de foto's-pagina — dit bestand laadt dat script en luistert
   alleen naar het change-event van de onderliggende <select>. */
(function () {
  const form = document.getElementById("klus-zoekform");
  const zoekveld = form && form.querySelector('input[name="q"]');
  const klusKeuze = document.querySelector('select[name="klus"]');
  if (!form || !zoekveld) return;

  let volgnummer = 0;

  function huidigeLijst() {
    return document.querySelector(".klussenlijst-resultaten");
  }

  function verversen() {
    const eigen = ++volgnummer;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();

    fetch(url)
      .then(function (antwoord) { return antwoord.text(); })
      .then(function (html) {
        if (eigen !== volgnummer) return; // een nieuwere aanvraag is al onderweg
        const nieuweLijst = new DOMParser()
          .parseFromString(html, "text/html")
          .querySelector(".klussenlijst-resultaten");
        const oudeLijst = huidigeLijst();
        if (nieuweLijst && oudeLijst) oudeLijst.replaceWith(nieuweLijst);
        history.replaceState(null, "", url);
      })
      .catch(function () {
        // Geen verbinding of iets anders mis: gewoon submitten als vangnet.
        form.submit();
      });
  }

  let timer = null;
  zoekveld.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(verversen, 300);
  });

  if (klusKeuze) {
    // Was this.form.submit() (zie klussen.html); dat gaf een volledige reload.
    klusKeuze.removeAttribute("onchange");
    klusKeuze.addEventListener("change", verversen);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(timer);
    verversen();
  });

  initKlusKiezer("klus-kiezer", "klus-select");
})();
