/* Django-meldingen (zie basis.html, .meldingen) verdwijnen vanzelf na een
   paar seconden i.p.v. te blijven staan tot de volgende paginawissel. Eerst
   de fade-out klasse (animatie in app.css) en dan pas verwijderen, met een
   vangnet-timeout voor het geval animationend niet vuurt — zelfde opzet als
   klus-overgang.js. */
document.addEventListener("DOMContentLoaded", function () {
  var meldingen = document.querySelectorAll(".meldingen .melding");
  meldingen.forEach(function (melding, index) {
    setTimeout(function () {
      var weg = function () {
        melding.removeEventListener("animationend", weg);
        melding.remove();
      };
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        weg();
        return;
      }
      melding.addEventListener("animationend", weg);
      melding.classList.add("melding-uit");
      setTimeout(weg, 300);
    }, 3200 + index * 400);
  });
});
