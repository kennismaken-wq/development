/* Open/sluit-animatie voor een <dialog> die er op een telefoon als bottom
   sheet uitziet (zie "TELEFOON: BOTTOM SHEET" in app.css, dialog.uren-invoegen).

   showModal()/close() zetten `display` synchroon om — zonder omweg is er
   niets om te animeren, de sheet knalt in of uit beeld. Daarom een klasse
   die de overgang (transform: translateY) in gang zet, ná showModal(), en
   weer weg vóór close(). */
window.openSheet = function (dialoog) {
  dialoog.showModal();
  // Twee frames wachten: het eerste laat de browser de dichte stand
  // (translateY 100%) echt tekenen; pas het tweede mag de overgang naar
  // open in gang zetten. Eén frame is soms te vroeg — dan ziet de browser
  // geen verschil tussen "net getoond" en "open" en slaat de animatie over.
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      dialoog.classList.add("open-anim");
    });
  });
};

window.closeSheet = function (dialoog) {
  dialoog.classList.remove("open-anim");
  const klaar = function () {
    dialoog.removeEventListener("transitionend", klaar);
    dialoog.close();
  };
  dialoog.addEventListener("transitionend", klaar);
  // Vangnet: geen transitionend (breed scherm zonder animatie, of een
  // browser die 'm om wat voor reden dan ook niet vuurt) mag de dialoog niet
  // voorgoed open laten staan.
  setTimeout(function () {
    if (dialoog.open) {
      dialoog.removeEventListener("transitionend", klaar);
      dialoog.close();
    }
  }, 300);
};
