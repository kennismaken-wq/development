/* Urenexport: periode kiezen met een begin- en einddatum die openklapt.

   Dicht zie je twee velden naast elkaar: Begin en Eind. Tik je op een van
   de twee, dan klapt eronder een maandkalender open en kies je díé datum.
   Na het begin springt de keuze vanzelf door naar het eind; na het eind
   gaat het formulier meteen weg, net als de medewerkerkeuze eronder. Een
   einddatum vóór het begin wordt het nieuwe begin. Met de muis zie je de
   periode al voordat je tikt; Esc of ernaast tikken klapt dicht zonder iets
   te veranderen.

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
  var kort = new Intl.DateTimeFormat("nl-NL", { day: "numeric", month: "short", year: "numeric" });
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
  function eersteVan(d) {
    return new Date(d.getFullYear(), d.getMonth(), 1);
  }

  var vandaag = new Date();
  vandaag = new Date(vandaag.getFullYear(), vandaag.getMonth(), vandaag.getDate());

  var van, tot;
  var kant = null;        // "van" of "tot": welke datum je nu kiest; null = dicht
  var voorbeeld = null;   // dag onder de muis terwijl je kiest
  var focusDag, maand;

  function uitVelden() {
    van = uitIso(vanVeld.value) || vandaag;
    tot = uitIso(totVeld.value) || van;
  }

  // ── opbouw ──
  var kalender = document.createElement("div");
  kalender.className = "periodekiezer";
  kalender.innerHTML =
    '<div class="pk-velden">' +
    '  <button type="button" class="pk-veld" data-kant="van" aria-expanded="false">' +
    '    <span class="pk-veldlabel">Begin</span><span class="pk-waarde"></span>' +
    "  </button>" +
    '  <span class="pk-pijl" aria-hidden="true">→</span>' +
    '  <button type="button" class="pk-veld" data-kant="tot" aria-expanded="false">' +
    '    <span class="pk-veldlabel">Eind</span><span class="pk-waarde"></span>' +
    "  </button>" +
    "</div>" +
    '<div class="periodekalender" hidden>' +
    '  <div class="pk-kop">' +
    '    <button type="button" class="urenpijl" data-stap="-1" aria-label="Vorige maand">‹</button>' +
    '    <span class="pk-titel" aria-live="polite"></span>' +
    '    <button type="button" class="urenpijl" data-stap="1" aria-label="Volgende maand">›</button>' +
    "  </div>" +
    '  <table class="pk-raster" role="grid">' +
    "    <thead><tr>" + DAGEN.map(function (d) { return '<th scope="col">' + d + "</th>"; }).join("") + "</tr></thead>" +
    "    <tbody></tbody>" +
    "  </table>" +
    '  <p class="pk-hint" aria-live="polite"></p>' +
    "</div>";
  veld.hidden = true;
  veld.parentNode.insertBefore(kalender, veld);

  var velden = kalender.querySelectorAll(".pk-veld");
  var paneel = kalender.querySelector(".periodekalender");
  var titel = kalender.querySelector(".pk-titel");
  var lichaam = kalender.querySelector("tbody");
  var hint = kalender.querySelector(".pk-hint");
  kalender.querySelector(".pk-raster").setAttribute("aria-labelledby", veld.getAttribute("aria-labelledby"));

  function veldenBijwerken() {
    velden.forEach(function (knop) {
      var datum = knop.dataset.kant === "van" ? van : tot;
      knop.querySelector(".pk-waarde").textContent = kort.format(datum);
      knop.classList.toggle("actief", knop.dataset.kant === kant);
      knop.setAttribute("aria-expanded", kant ? "true" : "false");
    });
  }

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
    var begin = kant === "van" && voorbeeld ? voorbeeld : van;
    var eind = kant === "tot" && voorbeeld ? voorbeeld : tot;
    if (eind < begin) {
      // Voorbeeld aan de verkeerde kant: laat zien wat het wordt als je tikt.
      if (kant === "van") eind = begin; else begin = eind;
    }
    lichaam.querySelectorAll("button").forEach(function (knop) {
      var dag = uitIso(knop.dataset.dag);
      var cel = knop.parentNode;
      cel.classList.toggle("in-periode", dag >= begin && dag <= eind);
      cel.classList.toggle("begin", zelfdeDag(dag, begin));
      cel.classList.toggle("eind", zelfdeDag(dag, eind));
      knop.setAttribute("aria-pressed", dag >= begin && dag <= eind ? "true" : "false");
      knop.tabIndex = zelfdeDag(dag, focusDag) ? 0 : -1;
    });
    hint.textContent = kant === "van" ? "Kies de begindatum" : "Kies de einddatum";
  }

  function openen(welke) {
    kant = welke;
    voorbeeld = null;
    focusDag = welke === "van" ? van : tot;
    maand = eersteVan(focusDag);
    paneel.hidden = false;
    veldenBijwerken();
    tekenen();
  }

  function sluiten() {
    kant = null;
    uitVelden();
    paneel.hidden = true;
    veldenBijwerken();
  }

  function naarMaandVan(dag) {
    if (dag.getFullYear() !== maand.getFullYear() || dag.getMonth() !== maand.getMonth()) {
      maand = eersteVan(dag);
      tekenen();
    }
  }

  function kiezen(dag) {
    voorbeeld = null;
    focusDag = dag;
    if (kant === "van") {
      van = dag;
      if (tot < van) tot = van;
      kant = "tot";
      veldenBijwerken();
      markeren();
      return;
    }
    // Eind vóór het begin: dan is dit het nieuwe begin en blijf je het eind kiezen.
    if (dag < van) {
      van = dag;
      veldenBijwerken();
      markeren();
      return;
    }
    tot = dag;
    vanVeld.value = alsIso(van);
    totVeld.value = alsIso(tot);
    kant = null;
    veldenBijwerken();
    markeren();
    formulier.submit();
  }

  // ── bediening ──
  velden.forEach(function (knop) {
    knop.addEventListener("click", function () {
      if (kant === knop.dataset.kant) sluiten(); else openen(knop.dataset.kant);
    });
  });

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
    if (!knop) return;
    voorbeeld = uitIso(knop.dataset.dag);
    markeren();
  });
  lichaam.addEventListener("mouseleave", function () {
    voorbeeld = null;
    markeren();
  });

  document.addEventListener("click", function (e) {
    if (kant && !kalender.contains(e.target)) sluiten();
  });

  var PIJLTOETSEN = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
  kalender.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && kant) {
      var terug = kalender.querySelector('.pk-veld[data-kant="' + kant + '"]');
      sluiten();
      terug.focus();
      return;
    }
    if (!(e.key in PIJLTOETSEN) || !e.target.closest("button[data-dag]")) return;
    e.preventDefault();
    focusDag = dagErbij(focusDag, PIJLTOETSEN[e.key]);
    voorbeeld = focusDag;
    naarMaandVan(focusDag);
    markeren();
    lichaam.querySelector('button[data-dag="' + alsIso(focusDag) + '"]').focus();
  });

  uitVelden();
  veldenBijwerken();
})();
