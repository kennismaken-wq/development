/* Bouwt bovenop een <select> (die de bron van waarheid blijft voor het
   formulier) een zoekbare knop + lijst, voor als er te veel klussen zijn om
   zomaar in een kale keuzelijst te vinden. Kiezen in de lijst zet gewoon
   select.value en vuurt een "change"-event, dus de pagina die dit aanroept
   hoeft alleen naar dat event te luisteren.

   Gedeeld door drie schermen — zelfde widget, andere pillen boven de lijst,
   want per scherm is een andere as van de klussenlijst de verwarrende:

     Galerij (fotozoeken.js)                  staat  Alle/Actief/Niet actief
     uren schrijven (_uurblokformulier.html)  soort  Alle/Eenmalig/Onderhoud
     foto posten (_uploadveld.html)           allebei, twee rijen onder elkaar

   Welke assen het worden zegt `opts.assen` (of `opts.scopes` voor één rij).
   Elke as leest zijn waarde uit een eigen data-attribuut op de <option>s —
   `kenmerk: "scope"` leest `data-scope`, `"soort"` leest `data-soort` — en de
   waarde "altijd" staat voor een optie die onder elke pil zichtbaar blijft
   (de lege keuze: "Alle klussen", "Kies een klus", "Algemeen"). Bij meer dan
   één as moet een optie aan álle assen tegelijk voldoen.

   `opts.initialScope` zet welke pil van de eerste as al aanstaat als de kiezer
   opent (default "altijd"); `opts.onScopeChange(scope)` is optioneel en wordt
   aangeroepen als er op een andere pil geklikt wordt — de Galerij gebruikt dat
   om ook het fotoraster mee te filteren, niet alleen de opties in de kiezer
   zelf. Op de twee formulieren filteren de pillen alleen de lijst: daar kies
   je een klus, je filtert geen pagina.

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

  /* De assen waaruit een scherm kan kiezen, op naam (zie `data-pillen` in de
     templates). `kenmerk` is het data-attribuut op de <option> waar de as zijn
     waarde uit leest. */
  const KLUS_KIEZER_ASSEN = {
    // Galerij: welke klussen lopen er nog? (zie klussen/fotos.html, dat zijn
    // opties zelf schrijft en daarom nog data-scope gebruikt)
    status: {
      kenmerk: "scope",
      pillen: [
        { waarde: "altijd", tekst: "Alle" },
        { waarde: "actief", tekst: "Actief" },
        { waarde: "inactief", tekst: "Niet actief" },
      ],
    },
    // Eenmalige klus of onderhoudsklant? De waarden zijn die van Klus.Soort in
    // de database — "aanleg" heet in beeld "Eenmalig".
    soort: {
      kenmerk: "soort",
      pillen: [
        { waarde: "altijd", tekst: "Alle" },
        { waarde: "aanleg", tekst: "Eenmalig" },
        { waarde: "onderhoud", tekst: "Onderhoud" },
      ],
    },
    // Zelfde as als `status`, maar met het woord van de klussenlijst
    // ("Afgerond" i.p.v. "Niet actief") en uit data-staat, zodat hij naast de
    // soort-as kan staan zonder dat de twee elkaars attribuut lezen.
    staat: {
      kenmerk: "staat",
      pillen: [
        { waarde: "altijd", tekst: "Alle" },
        { waarde: "actief", tekst: "Actief" },
        { waarde: "inactief", tekst: "Afgerond" },
      ],
    },
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
    const assen = opts.assen || [{ kenmerk: "scope", pillen: opts.scopes || KLUS_KIEZER_ASSEN.status.pillen }];
    // Eigen nummer per kiezer, anders delen twee kiezers op dezelfde pagina
    // één groep radio's en zet een klik op "Onderhoud" in de ene de pil van de
    // andere uit. Per as nog een eigen naam erbij, om dezelfde reden tussen de
    // twee rijen van één kiezer.
    const kiezerNummer = ++klusKiezerTeller;
    const radioNaam = function (as) { return "klus-" + as.kenmerk + "-" + kiezerNummer; };

    const opties = Array.from(select.options).map(function (optie) {
      return { waarde: optie.value, tekst: optie.textContent, kenmerken: optie.dataset };
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
      assen
        .map(function (as, nummer) {
          // Alleen de eerste as start op `initialScope`; een tweede rij begint
          // altijd op "Alle", anders zou de Galerij-stand ook de soort-pil
          // verzetten.
          const begin = nummer === 0 ? initialScope : "altijd";
          return (
            '<div class="keuzes klus-kiezer-scope">' +
            as.pillen
              .map(function (pil) {
                return (
                  '<label class="keuzepil scope"><input type="radio" name="' + radioNaam(as) + '" value="' + pil.waarde + '"' +
                  (begin === pil.waarde ? " checked" : "") +
                  '><span class="vlak">' + pil.tekst + "</span></label>"
                );
              })
              .join("") +
            "</div>"
          );
        })
        .join("") +
      '<ul class="klus-kiezer-lijst" role="listbox"></ul>' +
      '<p class="klus-kiezer-leeg" hidden>Geen klussen gevonden</p>';

    wrapper.appendChild(trigger);
    wrapper.appendChild(popover);
    wrapper.classList.add("js-klaar");

    const zoekveld = popover.querySelector('input[type="search"]');
    const lijst = popover.querySelector(".klus-kiezer-lijst");
    const leegmelding = popover.querySelector(".klus-kiezer-leeg");
    const scopeVelden = assen.map(function (as) {
      return { as: as, velden: Array.from(popover.querySelectorAll('input[name="' + radioNaam(as) + '"]')) };
    });

    opties.forEach(function (optie) {
      const li = document.createElement("li");
      const knop = document.createElement("button");
      knop.type = "button";
      knop.className = "klus-kiezer-item";
      knop.setAttribute("role", "option");
      knop.dataset.waarde = optie.waarde;
      assen.forEach(function (as) {
        knop.dataset[as.kenmerk] = optie.kenmerken[as.kenmerk] || "altijd";
      });
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

    function standVan(rij) {
      const gekozen = rij.velden.find(function (veld) { return veld.checked; });
      return gekozen ? gekozen.value : "altijd";
    }

    // De stand van de eerste as — dat is wat onScopeChange doorgeeft, want de
    // enige pagina die daarop meeluistert (de Galerij) heeft er maar één.
    function huidigeScope() {
      return scopeVelden.length ? standVan(scopeVelden[0]) : "altijd";
    }

    function filteren() {
      const zoekterm = zoekveld.value.trim().toLowerCase();
      let zichtbaar = 0;
      items.forEach(function (item) {
        // Bij twee rijen pillen moet een klus aan allebei voldoen; "altijd"
        // op de optie (de lege keuze) valt onder elke pil.
        const assenOk = scopeVelden.every(function (rij) {
          const stand = standVan(rij);
          const waarde = item.dataset[rij.as.kenmerk];
          return stand === "altijd" || waarde === "altijd" || waarde === stand;
        });
        const zoekOk = !zoekterm || item.dataset.tekst.indexOf(zoekterm) !== -1;
        const toon = assenOk && zoekOk;
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
    scopeVelden.forEach(function (rij) {
      rij.velden.forEach(function (veld) {
        veld.addEventListener("change", function () {
          filteren();
          if (opts.onScopeChange) opts.onScopeChange(huidigeScope());
        });
      });
    });

    bijwerkenLabel();
  }

  /* Voor kiezers die verder niets hoeven te doen dan een klus kiezen (de twee
     formulieren): zet `data-pillen` op de wrapper met de namen uit
     KLUS_KIEZER_ASSEN hierboven, komma-gescheiden voor meer dan één rij
     ("soort,staat" bij het foto posten), en dit script pakt hem vanzelf op —
     geen eigen scriptbestand per pagina nodig, zoals de Galerij dat met
     fotozoeken.js wél heeft omdat daar ook het fotoraster mee moet filteren.

     Een select die op slot staat (het uurblok-detail vóór een klik op het
     bewerk-potlood) slaan we over: die hoort er dan als gewone tekst te staan,
     niet als knop. uurblokbewerken.js roept dit opnieuw aan zodra de velden
     opengaan. */
  window.initKlusKiezers = function (root) {
    (root || document).querySelectorAll(".klus-kiezer[data-pillen]").forEach(function (wrapper) {
      const select = wrapper.querySelector("select");
      if (!select || select.disabled) return;
      initKlusKiezer(wrapper, select, {
        assen: wrapper.dataset.pillen
          .split(",")
          .map(function (naam) { return KLUS_KIEZER_ASSEN[naam.trim()]; })
          .filter(Boolean),
        knopLabel: wrapper.dataset.knoplabel,
      });
    });
  };

  window.initKlusKiezer = initKlusKiezer;
  window.initKlusKiezers(document);
})();
