/* Bewerk-potlood op het uurblok-detailscherm (uren/_uurblokdetail_inhoud.html):
   zonder javascript is het gewoon een link naar dezelfde pagina met
   ?bewerken=1 (de server levert de velden dan al open aan, zie
   uren.views._uurblok_detail_context). Met javascript zetten we de al
   aanwezige velden meteen open, zodat de sheet niet hoeft te herladen —
   zelfde truc als medewerkers/profiel.html voor de eigen gegevens. Opslaan
   en het prullenbakje staan al in de HTML (met hidden), dit script schuift
   ze alleen in/uit beeld. */
(function () {
  var knop = document.getElementById("uurblok-wijzig-knop");
  var formulier = document.getElementById("uurblokdetailformulier");
  var opslaan = document.getElementById("uurblok-opslaan-boven");
  var verwijderen = document.getElementById("uurblok-verwijder-knop");
  if (!knop || !formulier) return;

  knop.addEventListener("click", function (gebeurtenis) {
    gebeurtenis.preventDefault();
    formulier.querySelectorAll("[disabled]").forEach(function (veld) {
      veld.disabled = false;
    });
    knop.hidden = true;
    if (opslaan) opslaan.hidden = false;
    if (verwijderen) verwijderen.hidden = false;
    var eerste = formulier.querySelector("select:not([disabled]), input:not([disabled]), textarea:not([disabled])");
    if (eerste) eerste.focus();
  });
})();
