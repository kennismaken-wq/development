/* Verdeelt de tegels in het fotoraster over vaste kolommen (masonry), maar
   met rond-robin toewijzing (tegel i naar kolom i % aantal) in plaats van
   "naar de kortste kolom", zoals de meeste masonry-scripts doen. Dat laatste
   laat de volgorde verspringen zodra ergens een opvallend hoge foto tussen
   zit: de kortste kolom is dan opeens een andere dan waar de uploadvolgorde
   'm zou plaatsen. Rond-robin geeft dus kolommen van ongelijke lengte, maar
   de volgorde blijft altijd exact de uploadvolgorde.

   Draait meteen bij het inladen van dit bestand — dus zowel bij een gewone
   pagina-load als wanneer bottomsheet.js het via voerScriptsUit opnieuw
   uitvoert nadat de inhoud van een <dialog> ververst is (uren/_uurblokdetail_
   inhoud.html) — en verder:
   - bij het wisselen tussen het mobiele en het brede aantal kolommen
     (dezelfde 620px-grens als voorheen in app.css);
   - wanneer static/js/fotozoeken.js het raster ververst na een zoekopdracht
     (zie de aanroep van window.fotoRasterHerverdelen daar). */
(function () {
  const BREEDTE_QUERY = "(min-width: 620px)";

  function kolomAantal() {
    return window.matchMedia(BREEDTE_QUERY).matches ? 4 : 2;
  }

  function verdeel(raster) {
    const bestaandeKolommen = raster.querySelectorAll(":scope > .fotoraster-kolom");
    const items = [];
    if (bestaandeKolommen.length) {
      bestaandeKolommen.forEach(function (kolom) {
        items.push.apply(items, kolom.children);
      });
    } else {
      items.push.apply(items, raster.children);
    }
    if (!items.length) return;

    const aantal = kolomAantal();
    const kolommen = [];
    for (let i = 0; i < aantal; i++) {
      const kolom = document.createElement("div");
      kolom.className = "fotoraster-kolom";
      kolommen.push(kolom);
    }
    items.forEach(function (item, i) {
      kolommen[i % aantal].appendChild(item);
    });

    raster.innerHTML = "";
    raster.style.flexDirection = "row";
    kolommen.forEach(function (kolom) { raster.appendChild(kolom); });
  }

  window.fotoRasterHerverdelen = function () {
    document.querySelectorAll(".fotoraster").forEach(verdeel);
  };

  window.fotoRasterHerverdelen();

  if (!window.__fotoRasterMediaListener) {
    window.__fotoRasterMediaListener = true;
    window.matchMedia(BREEDTE_QUERY).addEventListener("change", window.fotoRasterHerverdelen);
  }
})();
