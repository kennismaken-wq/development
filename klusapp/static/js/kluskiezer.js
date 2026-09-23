/* Bouwt bovenop een <select> (die de bron van waarheid blijft voor het
   formulier) een zoekbare knop + lijst, voor als er te veel klussen zijn om
   zomaar in een kale keuzelijst te vinden. Kiezen in de lijst zet gewoon
   select.value en vuurt een "change"-event, dus de pagina die dit aanroept
   hoeft alleen naar dat event te luisteren.

   Gedeeld door de foto's-pagina (fotozoeken.js) en het urenformulier
   (uren/_uurblokformulier.html) — zelfde widget, twee plekken, maar met een
   andere rij pillen boven de lijst: op de Galerij filter je op status
   (Alle/Actief/Niet actief), bij het uren schrijven op soort
   (Alle/Eenmalig/Onderhoud). Welke rij het wordt zegt `opts.scopes`; de
   waarden daarvan moeten overeenkomen met het data-scope-attribuut op de
   <option>s, waarbij "altijd" staat voor een optie die onder elke pil
   zichtbaar blijft (de lege keuze, "Alle klussen").

   `opts.initialScope` zet welke pil al aanstaat als de kiezer opent (default
   "altijd"); `opts.onScopeChange(scope)` is optioneel en wordt aangeroepen
   als er op een andere pil geklikt wordt — de Galerij gebruikt dat om ook
   het fotoraster mee te filteren, niet alleen de opties in de kiezer zelf.
   Bij het urenformulier filtert de pil alleen de lijst: daar kies je een
   klus, je filtert geen pagina.

   Wrapper en select mogen als element of als id meegegeven worden. Als
   element, want twee urenformulieren (de "uren toevoegen"-sheet en het
   uurblok-detail) kunnen tegelijk in de pagina staan en hebben dan allebei
   een select met dezelfde door Django gegenereerde id.

   Alles zit in een IIFE met een guard erop omdat dit script twee keer kan
   draaien: het uurblok-detail komt als HTML-fragment binnen en
   bottomsheet.js/voerScriptsUit voert de <script>-tags daarin opnieuw uit.
   Een tweede uitvoering hoeft alleen nog de nieuwe kiezers op te pakken. */
(function () {
  if (window.initKlusKiezer) {
    window.initKlusKiezers(document);
    return;
  }

  const KLUS_KIEZER_SCOPES = {
    // Galerij: welke klussen lopen er nog? (zie klussen/fotos.html)
    status: [
      { waarde: "altijd", tekst: "Alle" },
      { waarde: "actief", tekst: "Actief" },
      { waarde: "inactief", tekst: "Niet actief" },
    ],
    // Uren schrijven: eenmalige klus of onderhoudsklant? De waarden zijn die
    // van Klus.Soort in de database — "aanleg" heet in beeld "Eenmalig".
    soort: [
      { waarde: "altijd", tekst: "Alle" },
      { waarde: "aanleg", tekst: "Eenmalig" },
      { waarde: "onderhoud", tekst: "Onderhoud" },
    ],
  };

  let klusKiezerTeller = 0;

  function initKlusKiezer(wrapper, select, opts) {
    wrapper = typeof wrapper === "string" ? document.getElementById(wrapper) : wrapper;
    select = typeof select === "string" ? document.getElementById(select) : select;
    if (!wrapper || !select) return;
    // Al eens gedaan: een tweede aanroep (het urenformulier initialiseert
    // opnieuw zodra het uurblok-detail van slot gaat) zou anders een tweede
    // knop en popover naast de eerste hangen.
    if (wrapper.classList.contains("js-klaar")) return;
    opts = opts || {};
    const initialScope = opts.initialScope || "altijd";
    const scopes = opts.scopes || KLUS_KIEZER_SCOPES.status;
    // Eigen naam per kiezer, anders delen twee kiezers op dezelfde pagina één
    // groep radio's en zet een klik op "Onderhoud" in de ene de pil van de
    // andere uit.
    const scopeNaam = "klus-scope-" + ++klusKiezerTeller;

    const opties = Array.from(select.options).map(function (optie) {
      return { waarde: optie.value, tekst: optie.textContent, scope: optie.dataset.scope || "altijd" };
    });

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "klus-kiezer-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", opts.knopLabel || "Filter op klus");
    trigger.innerHTML =
      '<span class="label"></span>' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
    const label = trigger.querySelector(".label");

    const popover = document.createElement("div");
    popover.className = "klus-kiezer-popover glas";
    popover.hidden = true;
    popover.innerHTML =
      '<div class="klus-kiezer-zoek">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.6" y2="16.6"/></svg>' +
        '<input type="search" placeholder="Zoek klus…" aria-label="Zoek klus">' +
      "</div>" +
      '<div class="keuzes klus-kiezer-scope">' +
        scopes
          .map(function (scope) {
            return (
              '<label class="keuzepil scope"><input type="radio" name="' + scopeNaam + '" value="' + scope.waarde + '"' +
              (initialScope === scope.waarde ? " checked" : "") +
              '><span class="vlak">' + scope.tekst + "</span></label>"
            );
          })
          .join("") +
      "</div>" +
      '<ul class="klus-kiezer-lijst" role="listbox"></ul>' +
      '<p class="klus-kiezer-leeg" hidden>Geen klussen gevonden</p>';

    wrapper.appendChild(trigger);
    wrapper.appendChild(popover);
    wrapper.classList.add("js-klaar");

    const zoekveld = popover.querySelector('input[type="search"]');
    const lijst = popover.querySelector(".klus-kiezer-lijst");
    const leegmelding = popover.querySelector(".klus-kiezer-leeg");
    const scopeVelden = Array.from(popover.querySelectorAll('input[name="' + scopeNaam + '"]'));

    opties.forEach(function (optie) {
      const li = document.createElement("li");
      const knop = document.createElement("button");
      knop.type = "button";
      knop.className = "klus-kiezer-item";
      knop.setAttribute("role", "option");
      knop.dataset.waarde = optie.waarde;
      knop.dataset.scope = optie.scope;
      knop.dataset.tekst = optie.tekst.toLowerCase();
      knop.textContent = optie.tekst;
      knop.addEventListener("click", function () {
        select.value = optie.waarde;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        bijwerkenLabel();
        sluiten();
      });
      li.appendChild(knop);
      lijst.appendChild(li);
    });

    const items = Array.from(lijst.querySelectorAll(".klus-kiezer-item"));

    function bijwerkenLabel() {
      const gekozen = select.options[select.selectedIndex];
      label.textContent = gekozen ? gekozen.textContent : opties.length ? opties[0].tekst : "";
      items.forEach(function (item) {
        item.setAttribute("aria-selected", item.dataset.waarde === select.value ? "true" : "false");
      });
    }

    function huidigeScope() {
      const gekozen = scopeVelden.find(function (veld) { return veld.checked; });
      return gekozen ? gekozen.value : "altijd";
    }

    function filteren() {
      const scope = huidigeScope();
      const zoekterm = zoekveld.value.trim().toLowerCase();
      let zichtbaar = 0;
      items.forEach(function (item) {
        const scopeOk = scope === "altijd" || item.dataset.scope === "altijd" || item.dataset.scope === scope;
        const zoekOk = !zoekterm || item.dataset.tekst.indexOf(zoekterm) !== -1;
        const toon = scopeOk && zoekOk;
        item.parentElement.hidden = !toon;
        if (toon) zichtbaar++;
      });
      leegmelding.hidden = zichtbaar !== 0;
    }

    function buitenKlik(e) {
      if (!wrapper.contains(e.target)) sluiten();
    }
    function toetsKlik(e) {
      if (e.key === "Escape") {
        sluiten();
        trigger.focus();
      }
    }

    function openen() {
      popover.hidden = false;
      trigger.setAttribute("aria-expanded", "true");
      zoekveld.value = "";
      filteren();
      zoekveld.focus();
      document.addEventListener("click", buitenKlik, true);
      document.addEventListener("keydown", toetsKlik);
    }

    function sluiten() {
      popover.hidden = true;
      trigger.setAttribute("aria-expanded", "false");
      document.removeEventListener("click", buitenKlik, true);
      document.removeEventListener("keydown", toetsKlik);
    }

    trigger.addEventListener("click", function () {
      if (popover.hidden) openen();
      else sluiten();
    });
    zoekveld.addEventListener("input", filteren);
    zoekveld.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        const eerste = items.find(function (item) { return !item.parentElement.hidden; });
        if (eerste) eerste.click();
      }
    });
    scopeVelden.forEach(function (veld) {
      veld.addEventListener("change", function () {
        filteren();
        if (opts.onScopeChange) opts.onScopeChange(huidigeScope());
      });
    });

    bijwerkenLabel();
  }

  /* Voor kiezers die verder niets hoeven te doen dan een klus kiezen (het
     urenformulier): zet data-pillen="soort" op de wrapper en dit script pakt
     hem vanzelf op — geen eigen scriptbestand per pagina nodig, zoals de
     Galerij dat met fotozoeken.js wél heeft omdat daar ook het fotoraster mee
     moet filteren.

     Een select die op slot staat (het uurblok-detail vóór een klik op het
     bewerk-potlood) slaan we over: die hoort er dan als gewone tekst te staan,
     niet als knop. uurblokbewerken.js roept dit opnieuw aan zodra de velden
     opengaan. */
  window.initKlusKiezers = function (root) {
    (root || document).querySelectorAll(".klus-kiezer[data-pillen]").forEach(function (wrapper) {
      const select = wrapper.querySelector("select");
      if (!select || select.disabled) return;
      initKlusKiezer(wrapper, select, {
        scopes: KLUS_KIEZER_SCOPES[wrapper.dataset.pillen],
        knopLabel: wrapper.dataset.knoplabel,
      });
    });
  };

  window.initKlusKiezer = initKlusKiezer;
  window.initKlusKiezers(document);
})();
