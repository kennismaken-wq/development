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

/* Vult een lege <dialog> met HTML die van de server wordt opgehaald en opent
    'm daarna als sheet — voor schermen die bestaande content tonen (zoals het
   uurblok-detail vanuit de agenda) in plaats van een leeg formulier dat er al
   in de pagina stond. Bij een netwerkfout valt dit terug op gewoon navigeren
   naar `terugvalHref`, zodat de link ook zonder JS/fetch blijft werken.

   innerHTML voert geen <script>-tags uit die erin zitten (o.a. de foto-popup
   in _fotoraster.html heeft die nodig) — daarom worden ze hier één voor één
   vervangen door een vers <script>-element, dat de browser wél uitvoert. */
window.laadEnOpenSheet = function (dialoog, url, terugvalHref) {
  fetch(url)
    .then(function (respons) {
      if (!respons.ok) throw new Error("laden mislukt: " + respons.status);
      return respons.text();
    })
    .then(function (html) {
      dialoog.innerHTML = html;
      dialoog.querySelectorAll("script").forEach(function (oud) {
        const nieuw = document.createElement("script");
        for (let i = 0; i < oud.attributes.length; i++) {
          nieuw.setAttribute(oud.attributes[i].name, oud.attributes[i].value);
        }
        nieuw.textContent = oud.textContent;
        oud.replaceWith(nieuw);
      });
      window.openSheet(dialoog);
    })
    .catch(function () {
      window.location.href = terugvalHref;
    });
};
