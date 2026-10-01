/* Mijn aanwezigheid (templates/uren/mijn_aanwezigheid.html): zoomen en
   naar vandaag scrollen, zoals op de werkplanning (werkplanning.js). Meer
   hoeft hier niet: dit bord is alleen om te kijken. De dagen zijn breder
   dan bij de eigenaar, want er staat maar één rij op. */
(function () {
  const bord = document.getElementById("aw-bord");
  if (!bord) return;
  const scroller = bord.closest(".wp-scroll");

  function naarKolom(k, vloeiend) {
    const kop = bord.querySelector('.wp-kop[data-k="' + Math.max(k, 0) + '"]');
    const namen = bord.querySelector(".bord-hoek");
    if (!kop || !namen) return;
    const verschil = kop.getBoundingClientRect().left
      - scroller.getBoundingClientRect().left - namen.offsetWidth;
    scroller.scrollTo({ left: scroller.scrollLeft + verschil, behavior: vloeiend ? "smooth" : "auto" });
  }

  // "Vandaag": staat vandaag op het bord, dan erheen scrollen in plaats van
  // de pagina opnieuw te laden.
  const naarVandaag = document.querySelector("[data-naar-vandaag]");
  if (naarVandaag) {
    naarVandaag.addEventListener("click", function (e) {
      const kop = bord.querySelector(".wp-kop.vandaag");
      if (!kop) return;
      e.preventDefault();
      naarKolom(Number(kop.dataset.k) - 1, true);
    });
  }

  // Zoom: hoe breed een dag is. Ruimer dan op de werkplanning (240/112/26).
  const ZOOM = { dag: 300, week: 150, maand: 34 };
  const zoomSleutel = "mijn-aanwezigheid-zoom";
  let zoom = "week";
  function zetZoom(nieuw) {
    if (!ZOOM[nieuw]) return;
    const links = Math.round(scroller.scrollLeft / ZOOM[zoom]);
    zoom = nieuw;
    bord.style.setProperty("--dag", ZOOM[zoom] + "px");
    Object.keys(ZOOM).forEach(function (z) {
      bord.classList.toggle("wp-zoom-" + z, z === zoom);
    });
    document.querySelectorAll("[data-zoom]").forEach(function (knop) {
      knop.classList.toggle("actief", knop.dataset.zoom === zoom);
      knop.setAttribute("aria-pressed", knop.dataset.zoom === zoom ? "true" : "false");
    });
    scroller.scrollLeft = links * ZOOM[zoom];
    try { localStorage.setItem(zoomSleutel, zoom); } catch (fout) { /* dan maar niet onthouden */ }
  }
  document.querySelectorAll("[data-zoom]").forEach(function (knop) {
    knop.addEventListener("click", function () { zetZoom(knop.dataset.zoom); });
  });
  let bewaard = null;
  try { bewaard = localStorage.getItem(zoomSleutel); } catch (fout) { /* dan week */ }
  zetZoom(bewaard || "week");

  // Open op vandaag (of de gekozen dag), met de dag ervoor nog in beeld.
  naarKolom(Number(bord.dataset.startkolom) - 1);
})();
