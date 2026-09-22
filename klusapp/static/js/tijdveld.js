/* Rondt een <input type="time" step="…"> af op het dichtstbijzijnde
   stapveelvoud.

   step regelt op een computer al hoe de pijltjes/scroll springen, maar niet
   elke telefoon houdt zich daaraan: met name Android's tijdkiezer laat de
   minuten gewoon per stuk scrollen, ongeacht step. Deze correctie zorgt dat
   de uiteindelijke waarde er ondanks dat toch op uitkomt. */
(function () {
  document.querySelectorAll('input[type="time"][step]').forEach(function (veld) {
    var stapMinuten = parseInt(veld.step, 10) / 60;
    if (!stapMinuten) return;

    veld.addEventListener("change", function () {
      if (!veld.value) return;
      var delen = veld.value.split(":");
      var totaal = parseInt(delen[0], 10) * 60 + parseInt(delen[1], 10);
      // % 1440: een afronding naar boven vanaf bv. 23:52 mag niet naar de
      // volgende dag "overlopen", dat blijft gewoon 00:00 diezelfde dag.
      var afgerond = (Math.round(totaal / stapMinuten) * stapMinuten) % 1440;
      var uur = Math.floor(afgerond / 60);
      var minuut = afgerond % 60;
      veld.value = String(uur).padStart(2, "0") + ":" + String(minuut).padStart(2, "0");
    });
  });
})();
