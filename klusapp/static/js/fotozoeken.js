/* Live zoeken op de foto tab: bij elke toetsaanslag (met een korte pauze
   erin, zodat niet elke letter apart een verzoek stuurt) en bij het wisselen
   van klus haalt dit script dezelfde pagina opnieuw op en vervangt alleen het
   fotoraster — geen volledige page reload voor elke letter.

   Bewust géén los JSON/fragment-endpoint: dit haalt gewoon de normale
   fotos-pagina op en pakt er client-side het rasterdeel uit. Simpeler, en
   zonder JS (of zonder verbinding) werkt het gewone <form method=get>
   gewoon nog steeds. */
(function () {
  const form = document.getElementById("foto-zoekform");
  const zoekveld = form && form.querySelector('input[name="q"]');
  const klusKeuze = document.querySelector('select[name="klus"]');
  if (!form || !zoekveld) return;

  let volgnummer = 0;

  function huidigRaster() {
    return document.querySelector(".fotoraster-resultaten");
  }

  function verversen() {
    const eigen = ++volgnummer;
    const url = new URL(window.location.href);
    url.search = new URLSearchParams(new FormData(form)).toString();

    fetch(url)
      .then(function (antwoord) { return antwoord.text(); })
      .then(function (html) {
        if (eigen !== volgnummer) return; // een nieuwere aanvraag is al onderweg
        const nieuwRaster = new DOMParser()
          .parseFromString(html, "text/html")
          .querySelector(".fotoraster-resultaten");
        const oudRaster = huidigRaster();
        if (nieuwRaster && oudRaster) oudRaster.replaceWith(nieuwRaster);
        history.replaceState(null, "", url);
      })
      .catch(function () {
        // Geen verbinding of iets anders mis: gewoon submitten als vangnet.
        form.submit();
      });
  }

  let timer = null;
  zoekveld.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(verversen, 300);
  });

  if (klusKeuze) {
    // Was this.form.submit() (zie fotos.html); dat gaf een volledige reload.
    klusKeuze.removeAttribute("onchange");
    klusKeuze.addEventListener("change", verversen);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    clearTimeout(timer);
    verversen();
  });

  initKlusKiezer();

  /* Bouwt bovenop de <select name="klus"> (die de bron van waarheid blijft
     voor het formulier) een zoekbare knop + lijst, voor als er te veel
     klussen zijn om zomaar in een kale keuzelijst te vinden. Kiezen in de
     lijst zet gewoon select.value en vuurt een "change"-event, dus de
     bestaande klusKeuze-listener hierboven ververst het raster zoals altijd. */
  function initKlusKiezer() {
    const wrapper = document.getElementById("klus-kiezer");
    const select = document.getElementById("klus-select");
    if (!wrapper || !select) return;

    const opties = Array.from(select.options).map(function (optie) {
      return { waarde: optie.value, tekst: optie.textContent, scope: optie.dataset.scope || "altijd" };
    });

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "klus-kiezer-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-label", "Filter op klus");
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
        '<label class="keuzepil scope"><input type="radio" name="klus-scope" value="altijd" checked><span class="vlak">Alle</span></label>' +
        '<label class="keuzepil scope"><input type="radio" name="klus-scope" value="actief"><span class="vlak">Actief</span></label>' +
        '<label class="keuzepil scope"><input type="radio" name="klus-scope" value="inactief"><span class="vlak">Niet actief</span></label>' +
      "</div>" +
      '<ul class="klus-kiezer-lijst" role="listbox"></ul>' +
      '<p class="klus-kiezer-leeg" hidden>Geen klussen gevonden</p>';

    wrapper.appendChild(trigger);
    wrapper.appendChild(popover);
    wrapper.classList.add("js-klaar");

    const zoekveld = popover.querySelector('input[type="search"]');
    const lijst = popover.querySelector(".klus-kiezer-lijst");
    const leegmelding = popover.querySelector(".klus-kiezer-leeg");
    const scopeVelden = Array.from(popover.querySelectorAll('input[name="klus-scope"]'));

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
      label.textContent = gekozen ? gekozen.textContent : "Alle klussen";
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
    scopeVelden.forEach(function (veld) { veld.addEventListener("change", filteren); });

    bijwerkenLabel();
  }
})();
