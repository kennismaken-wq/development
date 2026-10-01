/* Slide-animatie voor het terugpijltje (zie app.css: .kaart.klus-uit-animatie).
   Dit onderschept de klik, start de uitschuifanimatie op de kaart en
   navigeert tegelijk; de browser houdt deze pagina in beeld tot de volgende
   er is, dus de animatie overbrugt het laden in plaats van erop te wachten.

   Vóór (deze regel staat als eerste, dus loopt vóór <body> is geparst — geen
   flits): als de vórige klik een terugpijl was, schuift deze kaart nu
   omgekeerd in (van links, zie html.klus-terug-navigatie in app.css)
   i.p.v. steeds van rechts, wat er anders uitziet alsof je een klus opnieuw
   "opent" terwijl je juist terugging. */
if (sessionStorage.getItem("klus-terug-navigatie")) {
  sessionStorage.removeItem("klus-terug-navigatie");
  document.documentElement.classList.add("klus-terug-navigatie");
}

/* Pagina terug uit de back-forward-cache (browser-terug, of history.back()
   hieronder): dan draait het script hierboven niet opnieuw. De kaart zou nog
   uitgeschoven staan, en het inschuiven moet hier alsnog gestart worden. */
window.addEventListener("pageshow", function (gebeurtenis) {
  if (!gebeurtenis.persisted) return;
  var kaart = document.querySelector(".kaart");
  if (kaart) kaart.classList.remove("klus-uit-animatie");
  var html = document.documentElement;
  html.classList.remove("klus-terug-navigatie");
  if (sessionStorage.getItem("klus-terug-navigatie")) {
    sessionStorage.removeItem("klus-terug-navigatie");
    void html.offsetWidth; // opnieuw starten, ook als de klasse er al stond
    html.classList.add("klus-terug-navigatie");
  }
});

/* Is het doel van het pijltje precies de pagina waar je net vandaan kwam?
   Dan is browser-terug hetzelfde, maar sneller: de browser toont die pagina
   vaak meteen uit zijn geheugen, op de plek waar je was gescrold. */
function isVorigePagina(doel) {
  if (!document.referrer || history.length < 2) return false;
  try {
    var vorige = new URL(document.referrer);
    var naar = new URL(doel, location.href);
    return vorige.origin === location.origin &&
      vorige.pathname + vorige.search === naar.pathname + naar.search;
  } catch (fout) {
    return false;
  }
}

document.addEventListener("click", function (gebeurtenis) {
  var pijl = gebeurtenis.target.closest(".terug-pijl");
  if (!pijl || gebeurtenis.button !== 0 || gebeurtenis.ctrlKey || gebeurtenis.metaKey || gebeurtenis.shiftKey) return;

  var doel = pijl.href;
  var terugInGeschiedenis = isVorigePagina(doel);
  var kaart = document.querySelector(".kaart");
  var animeren = kaart && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!terugInGeschiedenis && !animeren) return;

  gebeurtenis.preventDefault();
  // Uitschuiven en laden tegelijk, niet na elkaar: eerst de animatie
  // afwachten en dan pas de volgende pagina opvragen voelde traag. Het
  // uitschuiven wordt daardoor vaak afgebroken; het eigenlijke "terug"-gevoel
  // komt van de pagina waar je aankomt, die van links inschuift (de vlag).
  if (animeren) {
    kaart.classList.add("klus-uit-animatie");
    sessionStorage.setItem("klus-terug-navigatie", "1");
  }
  if (terugInGeschiedenis) {
    history.back();
  } else {
    window.location.href = doel;
  }
});
