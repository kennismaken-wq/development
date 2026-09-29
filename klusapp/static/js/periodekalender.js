/* Urenexport: periode kiezen in een kalender, met begin- en einddatum.

   Eerste tik is de begindatum, tweede tik de einddatum (tikt je eerder dan
   het begin, dan wordt dat het begin). Na de tweede tik gaat het formulier
   meteen weg, net als de medewerkerkeuze eronder. Tussendoor laat de
   kalender met de muis al zien welke periode het wordt; Esc breekt af.

   De kalender vult de twee datumvelden (van, tot) die de server verwacht
   (uren/views.py:_gekozen_periode). Zonder javascript blijven die gewoon
   zichtbaar en werkt het scherm ook. */
(function () {
  var veld = document.querySelector("[data-periodekalender]");
  if (!veld) return;

  var formulier = veld.closest("form");
  var vanVeld = veld.querySelector("[name=van]");
  var totVeld = veld.querySelector("[name=tot]");

  var DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"];
  var maandnaam = new Intl.DateTimeFormat("nl-NL", { month: "long", year: "numeric" });
  var voluit = new Intl.DateTimeFormat("nl-NL", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  function uitIso(tekst) {
    var delen = (tekst || "").split("-").map(Number);
    return delen.length === 3 ? new Date(delen[0], delen[1] - 1, delen[2]) : null;
  }
  function alsIso(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function dagErbij(d, n) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  }
  function zelfdeDag(a, b) {
    return a && b && a.getTime() === b.getTime();
  }

  var vandaag = new Date();
  vandaag = new Date(vandaag.getFullYear(), vandaag.getMonth(), vandaag.getDate());

  var van = uitIso(vanVeld.value) || vandaag;
  var tot = uitIso(totVeld.value) || van;
  var bezig = false;      // begin gekozen, wacht op het einde
  var voorbeeld = null;   // einddatum onder de muis terwijl je kiest
  var focusDag = van;
  var maand = new Date(van.getFullYear(), van.getMonth(), 1);

  // ── opbouw ──
  var kalender = document.createElement("div");
  kalender.className = "periodekalender";
  kalender.innerHTML =
    '<div class="pk-kop">' +
    '  <button type="button" class="urenpijl" data-stap="-1" aria-label="Vorige maand">‹</button>' +
    '  <span class="pk-titel" aria-live="polite"></span>' +
    '  <button type="button" class="urenpijl" data-stap="1" aria-label="Volgende maand">›</button>' +
    "</div>" +
    '<table class="pk-raster" role="grid">' +
    "  <thead><tr>" + DAGEN.map(function (d) { return '<th scope="col">' + d + "</th>"; }).join("") + "</tr></thead>" +
    "  <tbody></tbody>" +
    "</table>" +
    '<p class="pk-hint" aria-live="polite"></p>';
  veld.hidden = true;
  veld.parentNode.insertBefore(kalender, veld);

  var titel = kalender.querySelector(".pk-titel");
  var lichaam = kalender.querySelector("tbody");
  var hint = kalender.querySelector(".pk-hint");
  kalender.querySelector(".pk-raster").setAttribute("aria-labelledby", veld.getAttribute("aria-labelledby"));

  function tekenen() {
    titel.textContent = maandnaam.format(maand);
    lichaam.innerHTML = "";
    // Altijd vanaf de maandag van de week waarin de maand begint.
    var dag = dagErbij(maand, -((maand.getDay() + 6) % 7));
    do {
      var rij = document.createElement("tr");
      for (var i = 0; i < 7; i++) {
        var cel = document.createElement("td");
        var knop = document.createElement("button");
        knop.type = "button";
        knop.textContent = dag.getDate();
        knop.dataset.dag = alsIso(dag);
        knop.setAttribute("aria-label", voluit.format(dag));
        if (dag.getMonth() !== maand.getMonth()) cel.classList.add("buiten");
        if (zelfdeDag(dag, vandaag)) knop.classList.add("vandaag");
        cel.appendChild(knop);
        rij.appendChild(cel);
        dag = dagErbij(dag, 1);
      }
      lichaam.appendChild(rij);
    } while (dag.getMonth() === maand.getMonth());
    markeren();
  }

  // Alleen klassen bijwerken, niet opnieuw tekenen: zo blijft de focus
  // staan terwijl de muis over de dagen beweegt.
  function markeren() {
    var begin = van;
    var eind = bezig ? voorbeeld || van : tot;
    if (eind < begin) { var t = begin; begin = eind; eind = t; }
    lichaam.querySelectorAll("button").forEach(function (knop) {
      var dag = uitIso(knop.dataset.dag);
      var cel = knop.parentNode;
      cel.classList.toggle("in-periode", dag >= begin && dag <= eind);
      cel.classList.toggle("begin", zelfdeDag(dag, begin));
      cel.classList.toggle("eind", zelfdeDag(dag, eind));
      knop.setAttribute("aria-pressed", dag >= begin && dag <= eind ? "true" : "false");
      knop.tabIndex = zelfdeDag(dag, focusDag) ? 0 : -1;
    });
    hint.textContent = bezig ? "Kies de einddatum" : "";
  }

  function naarMaandVan(dag) {
    if (dag.getFullYear() !== maand.getFullYear() || dag.getMonth() !== maand.getMonth()) {
      maand = new Date(dag.getFullYear(), dag.getMonth(), 1);
      tekenen();
    }
  }

  function kiezen(dag) {
    focusDag = dag;
    if (!bezig) {
      van = dag;
      tot = null;
      bezig = true;
      voorbeeld = null;
      markeren();
      return;
    }
    if (dag < van) { tot = van; van = dag; } else { tot = dag; }
    bezig = false;
    markeren();
    vanVeld.value = alsIso(van);
    totVeld.value = alsIso(tot);
    formulier.submit();
  }

  // ── bediening ──
  kalender.querySelectorAll("[data-stap]").forEach(function (pijl) {
    pijl.addEventListener("click", function () {
      maand = new Date(maand.getFullYear(), maand.getMonth() + Number(pijl.dataset.stap), 1);
      focusDag = maand;
      tekenen();
    });
  });

  lichaam.addEventListener("click", function (e) {
    var knop = e.target.closest("button[data-dag]");
    if (knop) kiezen(uitIso(knop.dataset.dag));
  });

  lichaam.addEventListener("mouseover", function (e) {
    var knop = e.target.closest("button[data-dag]");
    if (!bezig || !knop) return;
    voorbeeld = uitIso(knop.dataset.dag);
    markeren();
  });

  var PIJLTOETSEN = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  kalender.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && bezig) {
      van = uitIso(vanVeld.value) || vandaag;
      tot = uitIso(totVeld.value) || van;
      bezig = false;
      markeren();
      return;
    }
    if (!(e.key in PIJLTOETSEN) || !e.target.closest("button[data-dag]")) return;
    e.preventDefault();
    focusDag = dagErbij(focusDag, PIJLTOETSEN[e.key]);
    if (bezig) voorbeeld = focusDag;
    naarMaandVan(focusDag);
    markeren();
    lichaam.querySelector('button[data-dag="' + alsIso(focusDag) + '"]').focus();
  });

  tekenen();
})();
