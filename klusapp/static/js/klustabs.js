// Klusdossier: Documenten/Uren/Foto's als tabbladen i.p.v. alle drie onder
// elkaar — op een telefoon was dat een lange scroll voor je bij Foto's bent.
// De eerste tab staat al open in de server-gerenderde HTML (zie
// klussen/klus_detail.html), dit script hoeft dus alleen op een klik te
// reageren.
document.querySelectorAll(".tabbladen").forEach(function (groep) {
  var knoppen = groep.querySelectorAll(".tabblad");
  var panelen = groep.querySelectorAll(".tabblad-paneel");

  knoppen.forEach(function (knop) {
    knop.addEventListener("click", function () {
      var gekozen = knop.dataset.tab;
      knoppen.forEach(function (andere) {
        andere.classList.toggle("actief", andere === knop);
      });
      panelen.forEach(function (paneel) {
        paneel.hidden = paneel.dataset.tab !== gekozen;
      });
    });
  });
});
