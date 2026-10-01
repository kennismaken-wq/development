/* "Tot" begint waar "Van" ophoudt.

   De tijdkiezer van een telefoon opent op de gekozen waarde, en bij een leeg
   veld bovenaan de lijst. Zonder dit script stond "Tot" daardoor op 05:00
   terwijl je om 14:00 begon, en scrolde je eerst negen uur aan kwartieren
   voorbij (gesprek Maarten, 01-10-2026). Een eindtijd vóór de begintijd kan
   toch niet (zie uren.forms.UurblokForm.clean), dus die opties halen we weg in
   plaats van ze alleen grijs te maken: iOS laat grijze opties gewoon in het
   draaiwiel staan.

   Werkt op elk form.uurblokformulier, ook als dat pas later in de pagina komt
   (de uurblok-sheet en de "uren toevoegen"-dialoog). Bestand tegen twee keer
   draaien, net als kluskiezer.js: bottomsheet.js voert de scripts in een
   opgehaald fragment opnieuw uit. Zonder javascript staan alle tijden er en
   controleert de server. */
(function () {
  function alleOpties(eind) {
    if (!eind._alleOpties) {
      eind._alleOpties = Array.prototype.map.call(eind.options, function (o) {
        return [o.value, o.textContent];
      });
    }
    return eind._alleOpties;
  }

  function beperk(formulier) {
    var begin = formulier.querySelector('select[name="begintijd"]');
    var eind = formulier.querySelector('select[name="eindtijd"]');
    if (!begin || !eind) return;
    var vanaf = begin.value; // "HH:MM" vergelijkt als tekst gewoon goed
    var gekozen = eind.value;
    var houden = alleOpties(eind).filter(function (optie) {
      return optie[0] === "" || !vanaf || optie[0] > vanaf;
    });
    eind.innerHTML = "";
    houden.forEach(function (optie) {
      eind.add(new Option(optie[1], optie[0]));
    });
    eind.value = !vanaf || gekozen > vanaf ? gekozen : "";
  }

  document.querySelectorAll("form.uurblokformulier").forEach(beperk);

  if (window.tijdkiezerKlaar) return;
  window.tijdkiezerKlaar = true;
  document.addEventListener("change", function (gebeurtenis) {
    var veld = gebeurtenis.target;
    if (veld.name !== "begintijd") return;
    var formulier = veld.closest("form.uurblokformulier");
    if (formulier) beperk(formulier);
  });
})();
