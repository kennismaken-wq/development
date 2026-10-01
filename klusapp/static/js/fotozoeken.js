/* Live zoeken op de foto tab: bij elke toetsaanslag (met een korte pauze
   erin, zodat niet elke letter apart een verzoek stuurt), bij het wisselen
   van klus en bij het wisselen van een pil (Aanleg/Onderhoud, Actief/Niet
   actief) haalt dit
   script dezelfde pagina opnieuw op en vervangt alleen het fotoraster — geen
   volledige page reload voor elke letter.

   Bewust géén los JSON/fragment-endpoint: dit haalt gewoon de normale
   fotos-pagina op en pakt er client-side het rasterdeel uit. Simpeler, en
   zonder JS (of zonder verbinding) werkt het gewone <form method=get>
   gewoon nog steeds.

   De zoekbare klus-kiezer zelf (knop + popover) zit in static/js/kluskiezer.js,
   gedeeld met de klussenlijst — dit bestand laadt dat script. De scope-pil
   filtert hier, net als bij de klussenlijst, ook het fotoraster zelf (niet
   alleen de opties in de kiezer), dus die geeft dit bestand door als
   onScopeChange. */
(function () {
  const form = document.getElementById("foto-zoekform");
  const zoekveld = form && form.querySelector('input[name="q"]');
  const klusKeuze = document.querySelector('select[name="klus"]');
  if (!form || !zoekveld) return;

  let volgnummer = 0;

  function huidigRaster() {
    return document.querySelector(".fotoraster-resultaten");
  }

  function verversen() {
    const eigen = ++volgnummer;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();

    fetch(url)
      .then(function (antwoord) { return antwoord.text(); })
      .then(function (html) {
        if (eigen !== volgnummer) return; // een nieuwere aanvraag is al onderweg
        const nieuwRaster = new DOMParser()
          .parseFromString(html, "text/html")
          .querySelector(".fotoraster-resultaten");
        const oudRaster = huidigRaster();
        if (nieuwRaster && oudRaster) oudRaster.replaceWith(nieuwRaster);
        // .fotoraster-resultaten wordt hier vervangen, maar het <script>-tag
        // van fotoraster.js zit daarbuiten (zie _fotoraster.html) en wordt
        // dus niet opnieuw uitgevoerd — daarom hier expliciet aanroepen.
        if (window.fotoRasterHerverdelen) window.fotoRasterHerverdelen();
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
    // Was this.form.submit() (zie fotos.html); dat gaf een volledige reload.
    klusKeuze.removeAttribute("onchange");
    klusKeuze.addEventListener("change", verversen);
  }

  // Verborgen veld per pillenrij in het zoekformulier, zodat de stand ook in
  // de url en in een gewone submit meegaat. "altijd" (geen pil aan) laten we
  // weg: dat is de standaard.
  function zetVeld(naam, waarde) {
    let veld = form.querySelector('input[name="' + naam + '"]');
    if (waarde === "altijd") {
      if (veld) veld.remove();
      return;
    }
    if (!veld) {
      veld = document.createElement("input");
      veld.type = "hidden";
      veld.name = naam;
      form.appendChild(veld);
    }
    veld.value = waarde;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(timer);
    verversen();
  });

  const kiezerWrapper = document.getElementById("klus-kiezer");
  initKlusKiezer("klus-kiezer", "klus-select", {
    // Geen "Alle"-pillen hier: niets aan is alles, nog eens tikken zet uit.
    uitzetbaar: true,
    assen: [
      { kenmerk: "soort", pillen: [
        { waarde: "aanleg", tekst: "Aanleg" },
        { waarde: "onderhoud", tekst: "Onderhoud" },
      ] },
      { kenmerk: "scope", pillen: [
        { waarde: "actief", tekst: "Actief" },
        { waarde: "inactief", tekst: "Niet actief" },
      ] },
    ],
    beginstanden: kiezerWrapper ? { soort: kiezerWrapper.dataset.soort, scope: kiezerWrapper.dataset.scope } : undefined,
    onScopeChange: function (scope, standen) {
      zetVeld("soort", standen.soort);
      zetVeld("scope", standen.scope);
      verversen();
    },
  });
})();
