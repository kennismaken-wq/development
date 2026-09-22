/* Richting voor de pagina-overgang in app.css (@view-transition). De browser
   animeert cross-document navigaties vanzelf zodra beide pagina's
   @view-transition hebben, maar weet niet of dit "een klus openen" of "terug
   naar het overzicht" is — dat type zet je hier, vóór de navigatie start.
   Zonder ondersteuning (geen pageswap-event met viewTransition) doet dit
   bestand niets en navigeert de link zoals altijd. */
window.addEventListener("pageswap", function (gebeurtenis) {
  if (!gebeurtenis.viewTransition) return;
  var overgang = gebeurtenis.activation && gebeurtenis.activation.entry;
  if (!overgang) return;

  var isKlusDetail = function (pad) {
    return /^\/klussen\/\d+\/?$/.test(pad);
  };

  var doelPad = new URL(overgang.url).pathname;
  var huidigPad = location.pathname;

  if (isKlusDetail(doelPad) && !isKlusDetail(huidigPad)) {
    gebeurtenis.viewTransition.types.add("klus-open");
  } else if (isKlusDetail(huidigPad) && doelPad.replace(/\/$/, "") === "/klussen") {
    gebeurtenis.viewTransition.types.add("klus-terug");
  }
});
