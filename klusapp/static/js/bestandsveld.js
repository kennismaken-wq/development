/* Nederlandse, duim-vriendelijke knop voor een bestandsveld.

   Een <input type=file> tekent zijn eigen knop, met tekst uit de browser:
   op een Nederlandse telefoon staat er "Choose files" / "No file chosen", en
   dat is niet te vertalen of te vergroten. Daarom verbergen we het echte veld
   en zetten er een eigen label-knop en statusregel naast.

   Bewust vanuit JavaScript verbergen en niet vanuit de CSS: gaat dit script
   niet op (oude browser, script geblokkeerd), dan blijft het gewone
   bestandsveld gewoon staan en werkt uploaden nog steeds. */
(function () {
  const velden = document.querySelectorAll('input[type="file"]');

  // Standaard het documentje-icoon; een veld met data-knopicoon="foto" (zie
  // uren.forms.UurblokFotosForm) krijgt in plaats daarvan hetzelfde
  // galerij-icoon als de zijbalk (medewerkers.pictogrammen: "fotos") en de
  // "Galerij"-tegel — zelfde beeld, herkenbaar als "hier komt een foto bij".
  const ICOON_BESTAND =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<path d="M13 3H5a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8"/>' +
    '<path d="M17 3v6M20 6h-6"/></svg>';
  const ICOON_FOTO =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="3" y="4" width="18" height="16" rx="2.5"/>' +
    '<circle cx="8.5" cy="9.5" r="1.7"/>' +
    '<path d="M4 17l5-5 3 3 3-3.5 5 5.5"/></svg>';

  velden.forEach(function (veld) {
    // Het script kan twee keer op een pagina staan (los formulier plus de
    // uploaddialoog); zonder deze check krijgt zo'n veld twee knoppen.
    if (veld.classList.contains("bestandsveld-verborgen")) return;

    const isFotoveld = veld.dataset.knopicoon === "foto";
    const icoon = isFotoveld ? ICOON_FOTO : ICOON_BESTAND;
    const tekst = veld.dataset.knoptekst || "Bestanden kiezen";
    const meervoud = isFotoveld ? "foto's" : "bestanden";

    const knop = document.createElement("label");
    knop.className = "bestandsknop";
    knop.setAttribute("for", veld.id);
    knop.innerHTML = icoon + "<span>" + tekst + "</span>";

    const status = document.createElement("p");
    status.className = "bestandsstatus";
    status.textContent = "Nog niets gekozen";

    veld.classList.add("bestandsveld-verborgen");
    veld.insertAdjacentElement("afterend", knop);
    knop.insertAdjacentElement("afterend", status);

    veld.addEventListener("change", function () {
      const aantal = veld.files ? veld.files.length : 0;
      if (aantal === 0) {
        status.textContent = "Nog niets gekozen";
      } else if (aantal === 1) {
        status.textContent = veld.files[0].name;
      } else {
        status.textContent = aantal + " " + meervoud + " gekozen";
      }
    });
  });
})();
