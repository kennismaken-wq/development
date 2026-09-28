/* Weekoverzicht: filter op klus zonder de pagina te herladen.

   Het bord bevat altijd alle blokken van de week (uren/views.py:planbord);
   dit script verbergt de blokken van andere klussen en rekent de totalen
   opnieuw uit: per dag onderaan, per persoon in de kolom Week, en de week
   rechtsboven. De keuze gaat met replaceState in het adres (?klus=), zodat
   verversen, bladeren naar een andere week en het terugpijltje van een klus
   hem onthouden — zonder dat de terugknop van de browser door elke
   filterkeuze heen hoeft.

   Zonder javascript zijn de filterknoppen gewone links met ?klus=, en doet
   de server hetzelfde. */
(function () {
  var filter = document.getElementById("bord-filter");
  if (!filter) return;

  var chips = document.querySelectorAll(".bord-chip[data-klus]");
  var dagcellen = document.querySelectorAll(".bord-cel[data-rij][data-dag]");
  var knoppen = filter.querySelectorAll("a[data-klus]");
  var alleKnop = filter.querySelector("a.alle");
  var weeklabel = document.getElementById("bord-weeklabel");

  // Zelfde notatie als uren/kalender.py:als_decimaal — 8, 8,5, 3,25.
  function alsUren(minuten) {
    return (minuten / 60).toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
  }

  function toepassen(klus) {
    chips.forEach(function (chip) {
      chip.hidden = klus !== "" && chip.dataset.klus !== klus;
    });

    var perRij = {}, perDag = {}, week = 0;
    dagcellen.forEach(function (cel) {
      var minuten = 0;
      cel.querySelectorAll(".bord-chip:not([hidden])").forEach(function (chip) {
        minuten += Number(chip.dataset.minuten);
      });
      perRij[cel.dataset.rij] = (perRij[cel.dataset.rij] || 0) + minuten;
      perDag[cel.dataset.dag] = (perDag[cel.dataset.dag] || 0) + minuten;
      week += minuten;
    });

    document.querySelectorAll(".bord-week[data-rij]").forEach(function (cel) {
      var minuten = perRij[cel.dataset.rij] || 0;
      cel.innerHTML = minuten ? alsUren(minuten) + " u" : '<span class="bord-leeg">–</span>';
    });
    document.querySelectorAll(".bord-naam[data-rij]").forEach(function (naam) {
      naam.classList.toggle("zonder-uren", !perRij[naam.dataset.rij]);
    });
    document.querySelectorAll(".bord-voet[data-dag] .dagtotaal").forEach(function (totaal) {
      var minuten = perDag[totaal.parentNode.dataset.dag] || 0;
      totaal.textContent = minuten ? alsUren(minuten) + " u" : "";
    });
    document.getElementById("bord-weektotaal").textContent = alsUren(week);
    document.getElementById("bord-voettotaal").textContent = alsUren(week) + " u";
    weeklabel.textContent = klus ? "uur aan deze klus" : weeklabel.dataset.standaard;

    knoppen.forEach(function (knop) {
      var actief = klus !== "" && knop.dataset.klus === klus;
      knop.classList.toggle("actief", actief);
      if (actief) knop.setAttribute("aria-current", "true");
      else knop.removeAttribute("aria-current");
    });
    alleKnop.parentNode.hidden = klus === "";

    // Het adres en de bladerknoppen bijwerken, zodat de keuze meegaat.
    var adres = new URL(window.location.href);
    if (klus) adres.searchParams.set("klus", klus);
    else adres.searchParams.delete("klus");
    history.replaceState(null, "", adres.pathname + adres.search);
    document.querySelectorAll(".navlinks a").forEach(function (link) {
      var doel = new URL(link.href);
      if (klus) doel.searchParams.set("klus", klus);
      else doel.searchParams.delete("klus");
      link.href = doel.pathname + doel.search;
    });
  }

  knoppen.forEach(function (knop) {
    knop.addEventListener("click", function (e) {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      // nog een tik op de gekozen klus zet het filter uit
      var klus = knop.classList.contains("actief") ? "" : knop.dataset.klus;
      toepassen(klus);
    });
  });
})();
