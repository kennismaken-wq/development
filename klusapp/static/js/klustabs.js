// Klusdossier: Bestanden/Uren/Foto's/Documenten als tabbladen i.p.v. alles
// onder elkaar — op een telefoon was dat een lange scroll voor je bij Foto's
// bent. De eerste tab staat al open in de server-gerenderde HTML (zie
// klussen/klus_detail.html), dit script hoeft dus alleen op een klik te
// reageren. Een paneel met data-ook="bestanden" is ook zichtbaar bij die
// tab; data-actief op de groep laat de CSS de tussenkopjes tonen.
document.querySelectorAll(".tabbladen").forEach(function (groep) {
  var knoppen = groep.querySelectorAll(".tabblad");
  var panelen = groep.querySelectorAll(".tabblad-paneel");

  knoppen.forEach(function (knop) {
    knop.addEventListener("click", function () {
      var gekozen = knop.dataset.tab;
      knoppen.forEach(function (andere) {
        andere.classList.toggle("actief", andere === knop);
      });
      groep.dataset.actief = gekozen;
      panelen.forEach(function (paneel) {
        var ook = (paneel.dataset.ook || "").split(" ");
        paneel.hidden = paneel.dataset.tab !== gekozen && ook.indexOf(gekozen) === -1;
      });
    });
  });
});
