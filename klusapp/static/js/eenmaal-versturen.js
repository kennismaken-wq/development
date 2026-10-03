/* Een formulier maar één keer versturen.

   Wie in de bus op slecht 4G op Opslaan tikt en niets ziet gebeuren, tikt nog
   een keer. Zonder dit stonden er dan twee (bij de stresstest: vijf) dezelfde
   uurblokken, notities of klussen in de database (03-10-2026, B16).

   Hoe: na een echte verzending (niet tegengehouden door een bevestigingsvraag
   of een controle zoals bestandsveld.js) krijgt het formulier data-bezig, en
   elke volgende verzending van datzelfde formulier wordt genegeerd. De knop
   gaat níet op disabled: dan valt zijn name/value weg uit de post, en daar
   leunen formulieren met meerdere knoppen op (actie=...). Na een paar
   seconden mag het weer, voor het geval de verbinding echt wegviel.

   Formulieren die zelf met fetch versturen (het urenvenster) houden het daar
   zelf bij; dit script ziet hun verzending als "tegengehouden". */
(function () {
  var WACHTTIJD = 6000;

  document.addEventListener(
    "submit",
    function (gebeurtenis) {
      if (gebeurtenis.target.dataset.bezig) {
        gebeurtenis.preventDefault();
        gebeurtenis.stopImmediatePropagation();
      }
    },
    true
  );

  document.addEventListener("submit", function (gebeurtenis) {
    var formulier = gebeurtenis.target;
    if (gebeurtenis.defaultPrevented) return;
    formulier.dataset.bezig = "1";
    formulier.querySelectorAll('button[type="submit"], button:not([type])').forEach(function (knop) {
      knop.setAttribute("aria-busy", "true");
    });
    // Ook knoppen buiten het formulier (form="..."), zoals Opslaan rechtsboven.
    if (formulier.id) {
      document.querySelectorAll('button[form="' + formulier.id + '"]').forEach(function (knop) {
        knop.setAttribute("aria-busy", "true");
      });
    }
    setTimeout(function () {
      vrijgeven(formulier);
    }, WACHTTIJD);
  });

  function vrijgeven(formulier) {
    delete formulier.dataset.bezig;
    formulier.querySelectorAll('[aria-busy="true"]').forEach(function (knop) {
      knop.removeAttribute("aria-busy");
    });
    if (formulier.id) {
      document.querySelectorAll('button[form="' + formulier.id + '"][aria-busy]').forEach(function (knop) {
        knop.removeAttribute("aria-busy");
      });
    }
  }

  // Terug met de terugknop: de browser kan de pagina uit zijn geheugen
  // halen, met data-bezig er nog op. Dan moet je gewoon opnieuw kunnen.
  window.addEventListener("pageshow", function (gebeurtenis) {
    if (gebeurtenis.persisted) {
      document.querySelectorAll("form[data-bezig]").forEach(vrijgeven);
    }
  });
})();
