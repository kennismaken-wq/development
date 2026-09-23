/* Live zoeken en filteren op het klussenscherm: zelfde aanpak als
   static/js/fotozoeken.js voor de foto tab — bij elke toetsaanslag (met een
   korte pauze erin) en bij elke wissel in de filterrij haalt dit script
   dezelfde pagina opnieuw op en vervangt alleen de klussenlijst.

   Bewust géén los JSON/fragment-endpoint: dit haalt gewoon de normale
   klussen-pagina op en pakt er client-side het lijstdeel uit. Zonder JS (of
   zonder verbinding) werkt het gewone <form method=get> gewoon nog steeds.

   De filterrij zelf (soort-pillen plus "Ook afgeronde") is gewone HTML in
   klussen.html en hoort via het form-attribuut al bij de zoekbalk, dus
   FormData pikt hem vanzelf op; hier wordt alleen de verversing aangezwengeld.
   De zoekbare klus-kiezer die hier eerst onder stond is weg — zie de docstring
   van klussen.views.klus_lijst. static/js/kluskiezer.js blijft bestaan voor de
   Galerij, waar hij wél iets doet. */
(function () {
  const form = document.getElementById("klus-zoekform");
  const zoekveld = form && form.querySelector('input[name="q"]');
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

  // Alles in de filterrij (soort-pillen en "Ook afgeronde") ververst de lijst.
  // Zonder dit script submit de noscript-knop het formulier en werkt hetzelfde
  // filter gewoon, alleen met een volledige herlading.
  const filterrij = document.getElementById("klus-filters");
  if (filterrij) {
    filterrij.querySelectorAll("input").forEach(function (knop) {
      knop.addEventListener("change", verversen);
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(timer);
    verversen();
  });
})();
