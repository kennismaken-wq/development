/* Het aanmaak-/bewerkformulier van een klus slimmer maken, zonder er een
   ander formulier van te maken.

   Vier dingen, allemaal bovenop wat er zonder javascript ook al werkt:

     1. Opdrachtgever voorstellen terwijl je typt, uit de namen die er al zijn.
        Zo blijft de spelling consistent — zonder dat is het de ene keer
        "Fam. Vermeer" en de andere keer "vermeer", en is er geen enkele
        koppeling meer tussen de klussen van dezelfde klant.
     2. De adressen tonen die deze opdrachtgever al heeft. Voorinvullen, niet
        overerven: het adres blijft van de klus (een VvE heeft één naam en
        meerdere terreinen), het formulier stelt alleen voor wat het al weet.
     3. Waarschuwen als er op deze opdrachtgever + dit adres al een klus staat.
        Twee afspraken op één adres is een geldig geval; per ongeluk een tweede
        dossier maken waar de uren zich over verdelen niet. Dus een melding met
        een link erheen, geen blokkade.
     4. Een naam voorstellen en de startdatum verbergen bij onderhoud.

   De gegevens komen uit het json_script in klus_form.html (gevuld door
   klussen.opdrachtgevers) — één blok in de pagina, dus geen extra verzoek.

   Gaat dit script niet op, dan staat er een gewoon formulier met alle velden
   en valideert de server precies hetzelfde. */
(function () {
  const gegevensblok = document.getElementById("bekende-opdrachtgevers");
  const opdrachtgeverVeld = document.getElementById("id_opdrachtgever");
  const adresVeld = document.getElementById("id_adres");
  const plaatsVeld = document.getElementById("id_plaats");
  const naamVeld = document.getElementById("id_naam");
  const startdatumBlok = document.getElementById("veld-startdatum");
  const adressenBlok = document.getElementById("bekende-adressen");
  const botsingBlok = document.getElementById("klusbotsing");
  if (!gegevensblok || !opdrachtgeverVeld) return;

  let opdrachtgevers = [];
  try {
    opdrachtgevers = JSON.parse(gegevensblok.textContent) || [];
  } catch (e) {
    return; // onleesbare gegevens: dan gewoon een kaal formulier
  }

  // Zelfde vergelijking als klussen.opdrachtgevers._sleutel in Python:
  // dubbele spaties weg en hoofdletterongevoelig, zodat "Fam.  Vermeer" en
  // "fam. vermeer" dezelfde klant zijn.
  function sleutel(tekst) {
    return (tekst || "").trim().replace(/\s+/g, " ").toLowerCase();
  }

  function gekozenSoort() {
    const aan = document.querySelector("input[name=soort]:checked");
    return aan ? aan.value : "";
  }

  function huidigeOpdrachtgever() {
    const gezocht = sleutel(opdrachtgeverVeld.value);
    if (!gezocht) return null;
    return (
      opdrachtgevers.find(function (groep) {
        return sleutel(groep.naam) === gezocht;
      }) || null
    );
  }

  function huidigAdres(groep) {
    if (!groep) return null;
    const a = sleutel(adresVeld ? adresVeld.value : "");
    const p = sleutel(plaatsVeld ? plaatsVeld.value : "");
    return (
      groep.adressen.find(function (plek) {
        return sleutel(plek.adres) === a && sleutel(plek.plaats) === p;
      }) || null
    );
  }

  /* ── 1. Suggestielijst bij de opdrachtgever ──────────────────────────────
     Bewust niet met <datalist>: die dropdown is browser-eigen chrome en breekt
     de glasstijl. Dit is dezelfde lijst en dezelfde CSS-klasse als de
     adres-autocomplete ernaast (static/js/adres-zoeken.js). */
  const lijst = document.createElement("ul");
  lijst.className = "adres-suggesties";
  lijst.hidden = true;
  document.body.appendChild(lijst);

  function verbergLijst() {
    lijst.hidden = true;
    lijst.innerHTML = "";
  }

  function toonLijst(namen) {
    lijst.innerHTML = "";
    if (!namen.length) {
      verbergLijst();
      return;
    }
    namen.forEach(function (naam) {
      const regel = document.createElement("li");
      regel.textContent = naam;
      // mousedown i.p.v. click: vuurt vóór het blur-event dat de lijst verbergt.
      regel.addEventListener("mousedown", function (gebeurtenis) {
        gebeurtenis.preventDefault();
        opdrachtgeverVeld.value = naam;
        verbergLijst();
        opdrachtgeverGewijzigd();
      });
      lijst.appendChild(regel);
    });
    const rand = opdrachtgeverVeld.getBoundingClientRect();
    lijst.style.top = rand.bottom + "px";
    lijst.style.left = rand.left + "px";
    lijst.style.width = rand.width + "px";
    lijst.hidden = false;
  }

  function zoekOpdrachtgevers() {
    const getypt = sleutel(opdrachtgeverVeld.value);
    if (!getypt) {
      verbergLijst();
      return;
    }
    const treffers = opdrachtgevers
      .filter(function (groep) {
        const naam = sleutel(groep.naam);
        return naam.indexOf(getypt) !== -1 && naam !== getypt;
      })
      .slice(0, 8)
      .map(function (groep) {
        return groep.naam;
      });
    toonLijst(treffers);
  }

  /* ── 2. De adressen die deze opdrachtgever al heeft ──────────────────── */
  // Het adres dat dit script zelf heeft ingevuld. Alleen zo'n adres mag het
  // ook weer weghalen als je van opdrachtgever wisselt: wat Maarten zelf heeft
  // getypt blijft staan, ook als hij daarna de klantnaam nog corrigeert.
  let zelfIngevuldAdres = "";

  function tekenAdressen() {
    if (!adressenBlok) return;
    adressenBlok.innerHTML = "";
    const groep = huidigeOpdrachtgever();

    // Van opdrachtgever gewisseld terwijl het adres nog van de vorige is: dan
    // hoort dat adres hier niet meer te staan. Zonder deze stap krijgt een
    // klus van VvE Parkzicht het adres van Fam. Vermeer mee.
    if (adresVeld && zelfIngevuldAdres && adresVeld.value.trim() === zelfIngevuldAdres) {
      if (!huidigAdres(groep)) {
        adresVeld.value = "";
        if (plaatsVeld) plaatsVeld.value = "";
        zelfIngevuldAdres = "";
      }
    }

    // Eén bekend adres en het veld is nog leeg: dan gewoon invullen. Een rij
    // met één knop erbij is ruis — de winst zit in het geval met meerdere.
    if (groep && groep.adressen.length === 1 && adresVeld && !adresVeld.value.trim()) {
      adresVeld.value = groep.adressen[0].adres;
      zelfIngevuldAdres = groep.adressen[0].adres;
      if (plaatsVeld && !plaatsVeld.value.trim()) plaatsVeld.value = groep.adressen[0].plaats;
    }
    if (!groep || groep.adressen.length < 2) {
      adressenBlok.hidden = true;
      return;
    }

    const kop = document.createElement("label");
    kop.textContent = "Adressen van deze opdrachtgever";
    adressenBlok.appendChild(kop);

    const keuzes = document.createElement("div");
    keuzes.className = "keuzes";
    // Welke pil aan staat leiden we af uit de velden, niet uit de laatste
    // klik: deze rij wordt opnieuw opgebouwd zodra het adres verandert, dus
    // een onthouden klik is meteen weg. Zo klopt de stand ook als het
    // formulier terugkomt met een validatiefout.
    const gekozen = huidigAdres(groep);
    groep.adressen.forEach(function (plek, nummer) {
      const pil = document.createElement("label");
      pil.className = "keuzepil kies";
      const knop = document.createElement("input");
      knop.type = "radio";
      // Geen veld van het formulier: Django negeert deze naam bij het posten.
      knop.name = "bekend-adres";
      knop.value = String(nummer);
      knop.checked = plek === gekozen;
      const vlak = document.createElement("span");
      vlak.className = "vlak";
      vlak.textContent = [plek.adres, plek.plaats].filter(Boolean).join(", ") || "Zonder adres";
      knop.addEventListener("change", function () {
        if (adresVeld) adresVeld.value = plek.adres;
        if (plaatsVeld) plaatsVeld.value = plek.plaats;
        zelfIngevuldAdres = plek.adres;
        adresGewijzigd();
      });
      pil.appendChild(knop);
      pil.appendChild(vlak);
      keuzes.appendChild(pil);
    });

    const anders = document.createElement("label");
    anders.className = "keuzepil kies";
    const andersKnop = document.createElement("input");
    andersKnop.type = "radio";
    andersKnop.name = "bekend-adres";
    andersKnop.value = "";
    // Aan zodra er een adres staat dat bij geen van de bekende hoort — dan is
    // dit letterlijk een ander adres. Bij een leeg veld staat er niets aan.
    andersKnop.checked = Boolean(adresVeld && adresVeld.value.trim() && !gekozen);
    const andersVlak = document.createElement("span");
    andersVlak.className = "vlak";
    andersVlak.textContent = "Ander adres";
    andersKnop.addEventListener("change", function () {
      if (adresVeld) {
        adresVeld.value = "";
        adresVeld.focus();
      }
      if (plaatsVeld) plaatsVeld.value = "";
      zelfIngevuldAdres = "";
      adresGewijzigd();
    });
    anders.appendChild(andersKnop);
    anders.appendChild(andersVlak);
    keuzes.appendChild(anders);

    adressenBlok.appendChild(keuzes);
    adressenBlok.hidden = false;
  }

  /* ── 3. Staat hier al een klus? ──────────────────────────────────────────
     Geen blokkade: de knop zet de melding weg en laat je doorgaan. Dat is de
     eerlijke vorm, want beide uitkomsten zijn geldig — alleen wil je ze niet
     per ongeluk door elkaar halen. */
  let genegeerd = "";

  function tekenBotsing() {
    if (!botsingBlok) return false;
    botsingBlok.innerHTML = "";
    const groep = huidigeOpdrachtgever();
    const plek = huidigAdres(groep);
    const combinatie =
      sleutel(opdrachtgeverVeld.value) + "|" + sleutel(adresVeld ? adresVeld.value : "");
    if (!plek || !plek.klussen.length || genegeerd === combinatie) {
      botsingBlok.hidden = true;
      return false;
    }

    const kaart = document.createElement("div");
    kaart.className = "klusbotsing-kaart";

    const kop = document.createElement("p");
    kop.className = "klusbotsing-kop";
    kop.textContent =
      plek.klussen.length === 1 ? "Hier staat al een klus" : "Hier staan al klussen";
    kaart.appendChild(kop);

    plek.klussen.forEach(function (klus) {
      const regel = document.createElement("a");
      regel.className = "klusbotsing-regel";
      regel.href = klus.url;
      const badge = document.createElement("span");
      badge.className = "soort-badge";
      badge.textContent = klus.soort;
      const naam = document.createElement("span");
      naam.className = "naam";
      naam.textContent = klus.naam + (klus.actief ? "" : " (afgerond)");
      regel.appendChild(badge);
      regel.appendChild(naam);
      kaart.appendChild(regel);
    });

    const doorgaan = document.createElement("button");
    doorgaan.type = "button";
    doorgaan.className = "knop-stil";
    doorgaan.textContent = "Toch een aparte klus";
    doorgaan.addEventListener("click", function () {
      genegeerd = combinatie;
      botsingBlok.hidden = true;
      botsingBlok.innerHTML = "";
      if (naamVeld) naamVeld.focus();
    });
    kaart.appendChild(doorgaan);

    botsingBlok.appendChild(kaart);
    botsingBlok.hidden = false;
    return true;
  }

  /* ── 4. Naam voorstellen en de startdatum verbergen ───────────────────── */
  let naamZelfGetypt = Boolean(naamVeld && naamVeld.value.trim());
  let laatsteVoorstel = "";

  function stelNaamVoor(erIsAlEenKlus) {
    if (!naamVeld || naamZelfGetypt) return;
    // Bij een botsing niets voorstellen: alleen Maarten weet wat deze klus
    // onderscheidt van de klus die er al staat ("Snoeicontract", "Onderhoud
    // bestrating"), en dat kan een formulier niet raden. Bij een eenmalige
    // klus ook niet: die heeft een eigen naam ("Vijver Van Leeuwen"), en de
    // klantnaam zou botsen met het onderhoud van diezelfde klant.
    if (erIsAlEenKlus || gekozenSoort() !== "onderhoud") {
      if (naamVeld.value === laatsteVoorstel) naamVeld.value = "";
      laatsteVoorstel = "";
      return;
    }
    const klant = opdrachtgeverVeld.value.trim();
    if (!klant) return;
    const groep = huidigeOpdrachtgever();
    const adres = adresVeld ? adresVeld.value.trim() : "";
    // Heeft deze opdrachtgever al een adres in de app, dan onderscheidt de
    // klusnaam zich op het adres; anders is de klantnaam genoeg. Kort houden is
    // geen schoonheidswens: de chip op het planbord kapt af met een ellipsis
    // (.bord-chip .klus in app.css).
    const staart = groep && groep.adressen.length && adres ? adres : klant;
    laatsteVoorstel = "Onderhoud " + staart;
    naamVeld.value = laatsteVoorstel;
  }

  function regelStartdatum() {
    if (!startdatumBlok) return;
    startdatumBlok.hidden = gekozenSoort() === "onderhoud";
  }

  /* ── Alles bij elkaar ─────────────────────────────────────────────────── */
  function bijwerken() {
    tekenAdressen();
    const erIsAlEenKlus = tekenBotsing();
    stelNaamVoor(erIsAlEenKlus);
    regelStartdatum();
  }

  function opdrachtgeverGewijzigd() {
    genegeerd = "";
    bijwerken();
  }

  function adresGewijzigd() {
    genegeerd = "";
    bijwerken();
  }

  opdrachtgeverVeld.setAttribute("autocomplete", "off");
  opdrachtgeverVeld.addEventListener("input", function () {
    zoekOpdrachtgevers();
    opdrachtgeverGewijzigd();
  });
  opdrachtgeverVeld.addEventListener("blur", function () {
    setTimeout(verbergLijst, 150);
  });
  if (adresVeld) adresVeld.addEventListener("change", adresGewijzigd);
  if (plaatsVeld) plaatsVeld.addEventListener("change", adresGewijzigd);
  if (naamVeld) {
    naamVeld.addEventListener("input", function () {
      naamZelfGetypt = naamVeld.value.trim() !== "" && naamVeld.value !== laatsteVoorstel;
    });
  }
  document.querySelectorAll("input[name=soort]").forEach(function (knop) {
    knop.addEventListener("change", bijwerken);
  });

  window.addEventListener("scroll", verbergLijst, true);
  window.addEventListener("resize", verbergLijst);

  // Ook meteen bij het openen: een formulier dat terugkomt met een
  // validatiefout moet dezelfde staat tonen als waarin het werd verstuurd.
  bijwerken();
})();
