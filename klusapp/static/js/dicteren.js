/* Microfoonknop in een tekstvak: inspreken in plaats van typen. Voor de
   notities in het klusdossier en de werkzaamheden bij een uurblok — wie met
   modder aan zijn handen in de bus zit, typt niet graag.

   Werkt op elk <textarea data-dicteer>, ook als dat pas later in de pagina
   komt (de uurblok-sheet haalt zijn inhoud op als hij opengaat).

   De spraakherkenning is die van de browser zelf (Web Speech API): geen
   server, geen sleutel, geen kosten. Chrome stuurt het geluid daarvoor naar
   Google, Safari naar Apple. Firefox kan het niet; daar verschijnt de knop
   gewoon niet, en de microfoon op het toetsenbord van de telefoon werkt nog
   altijd. */
(function () {
  var Herkenning = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Herkenning) return;

  var MICROFOON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="9" y="3" width="6" height="11" rx="3"/>' +
    '<path d="M5 11a7 7 0 0 0 14 0"/><line x1="12" y1="18" x2="12" y2="21"/></svg>';

  var bezig = null; // { herkenning, veld, knop }

  function melding(tekst) {
    var lijst = document.querySelector(".meldingen");
    if (!lijst) {
      lijst = document.createElement("ul");
      lijst.className = "meldingen";
      lijst.setAttribute("role", "status");
      document.body.appendChild(lijst);
    }
    var regel = document.createElement("li");
    regel.className = "melding";
    regel.textContent = tekst;
    lijst.appendChild(regel);
    setTimeout(function () { regel.remove(); }, 4000);
  }

  function hoofdletter(tekst) {
    return tekst.charAt(0).toUpperCase() + tekst.slice(1);
  }

  /* Chrome op Android geeft bij doorlopend luisteren soms elk resultaat
     opnieuw mét alles wat ervoor al gezegd was. Begint een nieuw stuk met
     het vorige, dan vervangt het dat stuk in plaats van het te herhalen. */
  function plakAanElkaar(stukken) {
    var uit = [];
    stukken.forEach(function (stuk) {
      stuk = stuk.trim();
      if (!stuk) return;
      var vorige = uit[uit.length - 1];
      if (vorige && stuk.toLowerCase().indexOf(vorige.toLowerCase()) === 0) {
        uit[uit.length - 1] = stuk;
      } else {
        uit.push(stuk);
      }
    });
    return uit.join(" ");
  }

  function stop() {
    if (bezig) bezig.herkenning.stop();
  }

  function start(veld, knop) {
    stop();
    var herkenning = new Herkenning();
    herkenning.lang = "nl-NL";
    herkenning.continuous = true;
    herkenning.interimResults = true;

    // Wat er al stond blijft staan; het ingesprokene komt erachter.
    var basis = veld.value;
    var tussen = basis && !/\s$/.test(basis) ? " " : "";
    var nieuweZin = !basis.trim() || /[.!?]\s*$/.test(basis);

    herkenning.onresult = function (e) {
      var definitief = [];
      var voorlopig = "";
      for (var i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) definitief.push(e.results[i][0].transcript);
        else voorlopig += e.results[i][0].transcript;
      }
      var gezegd = plakAanElkaar(definitief.concat([voorlopig]));
      if (!gezegd) return;
      if (nieuweZin) gezegd = hoofdletter(gezegd);
      veld.value = (basis + tussen + gezegd).slice(0, veld.maxLength > 0 ? veld.maxLength : undefined);
      veld.scrollTop = veld.scrollHeight;
      veld.dispatchEvent(new Event("input", { bubbles: true }));
    };
    herkenning.onerror = function (e) {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        melding("Geef de browser toestemming om de microfoon te gebruiken.");
      } else if (e.error === "no-speech") {
        melding("Niets gehoord. Tik op de microfoon en praat maar.");
      } else if (e.error !== "aborted") {
        melding("Inspreken lukte niet. Probeer het nog eens of typ het in.");
      }
    };
    herkenning.onend = function () {
      knop.classList.remove("luistert");
      knop.setAttribute("aria-pressed", "false");
      knop.setAttribute("aria-label", "Inspreken");
      veld.dispatchEvent(new Event("change", { bubbles: true }));
      if (bezig && bezig.herkenning === herkenning) bezig = null;
    };

    bezig = { herkenning: herkenning, veld: veld, knop: knop };
    knop.classList.add("luistert");
    knop.setAttribute("aria-pressed", "true");
    knop.setAttribute("aria-label", "Stop met inspreken");
    try {
      herkenning.start();
    } catch (fout) {
      herkenning.onend();
    }
  }

  function bouw(veld) {
    if (veld.dataset.dicteerKlaar) return;
    veld.dataset.dicteerKlaar = "1";
    var omhulsel = document.createElement("span");
    omhulsel.className = "dicteer-veld";
    veld.parentNode.insertBefore(omhulsel, veld);
    omhulsel.appendChild(veld);

    var knop = document.createElement("button");
    knop.type = "button";
    knop.className = "dicteer-knop";
    knop.title = "Inspreken";
    knop.setAttribute("aria-label", "Inspreken");
    knop.setAttribute("aria-pressed", "false");
    knop.innerHTML = MICROFOON;
    knop.addEventListener("click", function () {
      if (veld.disabled || veld.readOnly) return;
      if (bezig && bezig.veld === veld) stop();
      else start(veld, knop);
    });
    omhulsel.appendChild(knop);
  }

  function zoek(binnen) {
    if (binnen.matches && binnen.matches("textarea[data-dicteer]")) bouw(binnen);
    if (binnen.querySelectorAll) binnen.querySelectorAll("textarea[data-dicteer]").forEach(bouw);
  }

  function begin() {
    zoek(document);
    new MutationObserver(function (wijzigingen) {
      wijzigingen.forEach(function (w) { w.addedNodes.forEach(zoek); });
    }).observe(document.body, { childList: true, subtree: true });
  }

  // Niet stiekem door blijven luisteren: bij versturen, een sheet die dichtgaat
  // of de telefoon die op slot gaat, stopt de microfoon.
  document.addEventListener("submit", stop, true);
  document.addEventListener("close", stop, true);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stop();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", begin);
  else begin();
})();
