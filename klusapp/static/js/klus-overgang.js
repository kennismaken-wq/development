/* Slide-animatie voor het terugpijltje (zie app.css: .kaart.klus-uit-animatie).
   Een gewone <a href> navigeert meteen weg — dan is er niets meer om te
   animeren. Dit onderschept de klik, speelt de uitschuifanimatie af op de
   kaart en navigeert pas daarna, zelfde opzet als bottomsheet.js
   (klasse toevoegen, op animationend wachten, met een vangnet-timeout voor
   het geval die niet vuurt). */
document.addEventListener("click", function (gebeurtenis) {
  var pijl = gebeurtenis.target.closest(".terug-pijl");
  if (!pijl) return;

  var kaart = document.querySelector(".kaart");
  if (!kaart || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  gebeurtenis.preventDefault();
  var doel = pijl.href;
  var vangnet;
  var weg = function () {
    kaart.removeEventListener("animationend", weg);
    clearTimeout(vangnet);
    window.location.href = doel;
  };
  kaart.addEventListener("animationend", weg);
  vangnet = setTimeout(weg, 300);
  kaart.classList.add("klus-uit-animatie");
});
