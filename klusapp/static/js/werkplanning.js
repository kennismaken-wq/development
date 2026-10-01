/* Werkplanning (templates/uren/aanwezigheid.html): cellen kiezen en zetten.

   Kiezen gaat zoals in Excel:
   - klik op een cel: die ene cel
   - slepen: een blok van de eerste tot de laatste cel (meer dagen, meer mensen)
   - shift-klik: een blok van de vorige cel tot deze
   - klik op een naam: al zijn dagen; klik op een dag: iedereen op die dag
   Daarna gaat het venster open en zet één formulier de hele selectie.
   Dat werkt in twee blokken die los van elkaar staan: de mensen (groen/rood,
   klussen per persoon) en daaronder de klussen (gepland of niet, met een
   notitie). Een selectie blijft binnen het blok waar je begon.
   Cellen van iemand die op die dag niet in dienst is, doen niet mee.

   Op een aanraakscherm schuift slepen het bord opzij in plaats van te
   kiezen; daar kiest een tik alleen die ene cel. Daar is dit scherm ook
   niet voor gemaakt. */
(function () {
  const bord = document.getElementById("wp-bord");
  const venster = document.getElementById("wp-cellen");
  const notitieVenster = document.getElementById("wp-notitie");
  if (!bord || !venster) return;

  const scroller = bord.closest(".wp-scroll");
  const cellen = Array.from(bord.querySelectorAll("button.wp-cel"));
  const kluscellen = Array.from(bord.querySelectorAll("button.wp-kc"));
  const klusVenster = document.getElementById("wp-klusdagen");
  const formulier = venster.querySelector("form");
  const celvelden = venster.querySelector("[data-cellen]");
  const titel = venster.querySelector(".wp-dialoogtitel");
  const sub = venster.querySelector("[data-sub]");
  const redenBlok = venster.querySelector("[data-reden-blok]");
  const opmerking = venster.querySelector("[name=opmerking]");
  const klussenBlok = venster.querySelector("[data-klussen-blok]");
  const klussenWijzigen = venster.querySelector("[name=klussen_wijzigen]");
  const klusZoek = venster.querySelector(".wp-kluszoek");
  const klusGemengd = venster.querySelector("[data-klus-gemengd]");
  const klusVinkjes = Array.from(venster.querySelectorAll("[name=klus]"));

  let anker = null;   // de cel waar het slepen of shift-klikken van uitgaat
  let sleept = false;

  function isKlus(cel) {
    return cel.classList.contains("wp-kc");
  }

  function groep(cel) {
    return isKlus(cel) ? kluscellen : cellen;
  }

  function plek(cel) {
    return { r: Number(isKlus(cel) ? cel.dataset.q : cel.dataset.r), k: Number(cel.dataset.k) };
  }

  function blok(van, tot) {
    const a = plek(van), b = plek(tot);
    const r1 = Math.min(a.r, b.r), r2 = Math.max(a.r, b.r);
    const k1 = Math.min(a.k, b.k), k2 = Math.max(a.k, b.k);
    return groep(van).filter(function (cel) {
      const p = plek(cel);
      return p.r >= r1 && p.r <= r2 && p.k >= k1 && p.k <= k2;
    });
  }

  function markeer(gekozen) {
    cellen.concat(kluscellen).forEach(function (cel) { cel.classList.remove("gekozen"); });
    gekozen.forEach(function (cel) { cel.classList.add("gekozen"); });
  }

  function gekozen() {
    return cellen.concat(kluscellen).filter(function (cel) { return cel.classList.contains("gekozen"); });
  }

  function openSelectie(lijst) {
    if (lijst.length && isKlus(lijst[0])) openKlusVenster(lijst);
    else openVenster(lijst);
  }

  // Eén waarde als alle gekozen cellen hem delen, anders null: dan staat er
  // in het venster niets voorgekozen en zet je bewust iets nieuws.
  // Lege velden staan niet in de html (een jaar telt duizenden cellen), dus
  // een ontbrekend data-attribuut is een lege waarde.
  function waarde(cel, sleutel) {
    return cel.dataset[sleutel] || "";
  }

  function gedeeld(lijst, sleutel) {
    const eerste = waarde(lijst[0], sleutel);
    return lijst.every(function (cel) { return waarde(cel, sleutel) === eerste; }) ? eerste : null;
  }

  function naamVan(cel) {
    const naam = bord.querySelector('.wp-naam[data-r="' + cel.dataset.r + '"] .wie');
    return naam ? naam.textContent.trim() : "";
  }

  function datumVan(cel) {
    const kop = bord.querySelector('.wp-kop[data-k="' + cel.dataset.k + '"]');
    return kop ? kop.dataset.datum : "";
  }

  // ── Notitie-popup ──────────────────────────────────────────────────────
  // Staat er een notitie in een cel die je niet (helemaal) kunt lezen —
  // in de maandzoom is een dag 26px, in de week valt een lange notitie weg
  // achter "…" — dan verschijnt hij bij aanwijzen meteen in een popje.
  // Zonder wachten, dus geen title: die komt pas na een seconde, en dan
  // stonden er twee. Leesbare notities en lege cellen houden de gewone
  // tooltip, die pas gemaakt wordt bij aanwijzen (niet voor 365 cellen
  // per rij vooraf in de html).
  const popje = document.createElement("div");
  popje.className = "wp-popje";
  popje.hidden = true;
  popje.innerHTML = '<span class="wp-popje-tekst"></span><span class="wp-popje-sub"></span>';
  document.body.appendChild(popje);
  let popjeCel = null;

  // Het element waar de notitie van deze cel op het scherm staat: de cel
  // zelf, of in een reeks (app.css, .reeks) de eerste cel daarvan.
  function getoondeTekst(cel) {
    let c = cel;
    const tekst = cel.querySelector(".tekst").textContent;
    for (let n = 0; c && n < 400; n++) {
      const t = c.querySelector(":scope > .tekst");
      if (!t || t.textContent !== tekst) return null;
      if (t.offsetParent !== null) return t;
      c = c.previousElementSibling;
    }
    return null;
  }

  function teKlein(cel) {
    const t = getoondeTekst(cel);
    return !t || t.scrollWidth > t.clientWidth + 1;
  }

  function toonPopje(cel) {
    const wie = cel.classList.contains("wp-notitie") ? "Notitie"
      : cel.dataset.q ? klusVan(cel).querySelector(".wie").textContent.trim() : naamVan(cel);
    const datum = cel.classList.contains("wp-notitie") ? cel.dataset.titel : datumVan(cel);
    popje.querySelector(".wp-popje-tekst").textContent = cel.querySelector(".tekst").textContent.trim();
    popje.querySelector(".wp-popje-sub").textContent = [wie, datum].filter(Boolean).join(" · ");
    popje.hidden = false;
    popjeCel = cel;
    // boven de cel, of eronder als daar geen plek is; nooit buiten beeld
    const r = cel.getBoundingClientRect();
    const b = popje.offsetWidth, h = popje.offsetHeight;
    const links = Math.min(Math.max(8, r.left + r.width / 2 - b / 2), window.innerWidth - b - 8);
    const boven = r.top - h - 6 < 8 ? r.bottom + 6 : r.top - h - 6;
    popje.style.left = links + "px";
    popje.style.top = boven + "px";
  }

  function verbergPopje() {
    popje.hidden = true;
    popjeCel = null;
  }

  bord.addEventListener("mouseover", function (e) {
    const cel = e.target.closest("button.wp-cel, button.wp-kc, button.wp-notitie");
    if (cel && cel === popjeCel) return;
    verbergPopje();
    if (!cel || sleept) return;
    if (cel.querySelector(".tekst") && teKlein(cel)) {
      cel.removeAttribute("title");
      toonPopje(cel);
      return;
    }
    if (cel.title || cel.classList.contains("wp-notitie")) return;
    const delen = [cel.dataset.q ? klusVan(cel).querySelector(".wie").textContent.trim() : naamVan(cel), datumVan(cel)];
    cel.querySelectorAll(".wp-kluslijn .naam, .tekst").forEach(function (t) {
      delen.push(t.textContent.trim());
    });
    cel.title = delen.filter(Boolean).join(" · ");
  });
  bord.addEventListener("mouseleave", verbergPopje);
  bord.addEventListener("mousedown", verbergPopje);
  scroller.addEventListener("scroll", verbergPopje, { passive: true });
  window.addEventListener("scroll", verbergPopje, { passive: true });

  function zetRadio(naam, waarde) {
    formulier.querySelectorAll("[name=" + naam + "]").forEach(function (keuze) {
      keuze.checked = waarde !== null && keuze.value === waarde;
    });
  }

  function toonReden() {
    const stand = formulier.querySelector("[name=stand]:checked");
    redenBlok.hidden = !stand || stand.value !== "nee";
    // wie afwezig is, gaat nergens heen: de server haalt zijn klussen weg
    klussenBlok.hidden = !!stand && stand.value === "nee";
    // Geen stand gekozen (gemengde selectie): de aanwezigheid blijft zoals
    // hij is, en een opmerking hoort bij die aanwezigheid, dus die ook.
    opmerking.closest("[data-opmerking-blok]").hidden = !stand;
  }

  function openVenster(lijst) {
    // Een tik op een aanraakscherm geeft zowel muisgebeurtenissen als een
    // click; het venster mag maar één keer open.
    if (!lijst.length || venster.open) return;
    markeer(lijst);

    celvelden.textContent = "";
    lijst.forEach(function (cel) {
      const veld = document.createElement("input");
      veld.type = "hidden";
      veld.name = "cel";
      veld.value = cel.dataset.cel;
      celvelden.appendChild(veld);
    });

    const mensen = new Set(lijst.map(function (cel) { return cel.dataset.r; })).size;
    const dagen = new Set(lijst.map(function (cel) { return cel.dataset.k; })).size;
    if (lijst.length === 1) {
      titel.textContent = naamVan(lijst[0]) + " · " + datumVan(lijst[0]);
    } else {
      titel.textContent = (mensen === 1 ? "1 persoon" : mensen + " mensen") + " · " +
        (dagen === 1 ? "1 dag" : dagen + " dagen");
    }
    sub.textContent = lijst.length === 1 ? "" : lijst.length + " cellen tegelijk";

    zetRadio("stand", gedeeld(lijst, "stand"));
    zetRadio("reden", gedeeld(lijst, "reden"));
    const tekst = gedeeld(lijst, "opmerking");
    opmerking.value = tekst === null ? "" : tekst;

    // Dezelfde klussen in elke cel: die staan aangevinkt, en opslaan zet
    // precies wat er dan aangevinkt is. Verschillende klussen: niets
    // aangevinkt, en alleen als je zelf iets aanvinkt gaan ze mee.
    const klussen = gedeeld(lijst, "klussen");
    const gekozenKlussen = klussen ? klussen.split(",") : [];
    klusVinkjes.forEach(function (vinkje) {
      vinkje.checked = gekozenKlussen.indexOf(vinkje.value) !== -1;
    });
    klussenWijzigen.value = klussen === null ? "0" : "1";
    klusGemengd.hidden = klussen !== null;
    klusZoek.value = "";
    filterKlussen();
    toonReden();

    window.openSheet(venster);
  }

  function filterKlussen() {
    const woorden = klusZoek.value.toLowerCase().split(/\s+/).filter(Boolean);
    klusVinkjes.forEach(function (vinkje) {
      const regel = vinkje.closest(".wp-klus");
      const tekst = regel.dataset.zoek;
      regel.hidden = !vinkje.checked && !woorden.every(function (w) { return tekst.indexOf(w) !== -1; });
    });
  }

  klusZoek.addEventListener("input", filterKlussen);
  // Enter in het zoekveld verstuurt anders het hele formulier.
  klusZoek.addEventListener("keydown", function (e) {
    if (e.key === "Enter") e.preventDefault();
  });

  formulier.addEventListener("change", function (e) {
    if (e.target.name === "klus") {
      klussenWijzigen.value = "1";
      klusGemengd.hidden = true;
    }
    toonReden();
  });

  // Muis: indrukken begint een selectie, eroverheen bewegen rekt hem op,
  // loslaten opent het venster.
  bord.addEventListener("mousedown", function (e) {
    const cel = e.target.closest("button.wp-cel, button.wp-kc");
    if (!cel || e.button !== 0) return;
    e.preventDefault();   // geen tekst selecteren tijdens het slepen
    if (e.shiftKey && anker && isKlus(anker) === isKlus(cel)) {
      markeer(blok(anker, cel));
    } else {
      anker = cel;
      markeer([cel]);
    }
    sleept = true;
  });

  bord.addEventListener("mouseover", function (e) {
    if (!sleept) return;
    const cel = e.target.closest("button.wp-cel, button.wp-kc");
    // binnen het blok blijven waar je begon
    if (cel && isKlus(cel) === isKlus(anker)) markeer(blok(anker, cel));
  });

  document.addEventListener("mouseup", function () {
    if (!sleept) return;
    sleept = false;
    openSelectie(gekozen());
  });

  // Toetsenbord en aanraken: een "click" zonder voorafgaande mousedown.
  bord.addEventListener("click", function (e) {
    const cel = e.target.closest("button.wp-cel, button.wp-kc");
    if (cel && e.detail === 0) {
      anker = cel;
      openSelectie([cel]);
      return;
    }

    if (e.target.closest("[data-namen-inklappen]")) {
      zetNamenSmal(!bord.classList.contains("namen-smal"));
      return;
    }

    const inklap = e.target.closest("[data-klussen-inklappen]");
    if (inklap) {
      zetKlussenDicht(!bord.classList.contains("klussen-dicht"));
      return;
    }

    const naam = e.target.closest(".wp-naam");
    if (naam) {
      openVenster(cellen.filter(function (c) { return c.dataset.r === naam.dataset.r; }));
      return;
    }
    const kop = e.target.closest(".wp-kop");
    if (kop) {
      openVenster(cellen.filter(function (c) { return c.dataset.k === kop.dataset.k; }));
      return;
    }

    const notitie = e.target.closest(".wp-notitie");
    if (notitie && notitieVenster) {
      const nf = notitieVenster.querySelector("form");
      nf.elements.datum.value = notitie.dataset.datum;
      nf.elements.tekst.value = notitie.dataset.tekst;
      notitieVenster.querySelector(".wp-dialoogtitel").textContent = notitie.dataset.titel;
      window.openSheet(notitieVenster);
      nf.elements.tekst.focus();
    }
  });

  [venster, notitieVenster, klusVenster].forEach(function (dialoog) {
    if (!dialoog) return;
    dialoog.querySelector("[data-sluit]").addEventListener("click", function () {
      window.closeSheet(dialoog);
    });
    // Klik naast het venster sluit het, net als Escape.
    dialoog.addEventListener("click", function (e) {
      if (e.target === dialoog) window.closeSheet(dialoog);
    });
    dialoog.addEventListener("close", function () { markeer([]); });
  });

  // ── Klussenblok ────────────────────────────────────────────────────────
  function klusVan(cel) {
    return bord.querySelector('.wp-klusnaam[data-q="' + cel.dataset.q + '"]');
  }

  function isoVan(cel) {
    const kop = bord.querySelector('.wp-kop[data-k="' + cel.dataset.k + '"]');
    return kop ? kop.dataset.iso : "";
  }

  function openKlusVenster(lijst) {
    if (!klusVenster || !lijst.length || klusVenster.open) return;
    markeer(lijst);
    const kf = klusVenster.querySelector("form");
    const velden = klusVenster.querySelector("[data-klusdagen]");
    velden.textContent = "";
    lijst.forEach(function (cel) {
      const veld = document.createElement("input");
      veld.type = "hidden";
      veld.name = "klusdag";
      veld.value = klusVan(cel).dataset.klus + ":" + isoVan(cel);
      velden.appendChild(veld);
    });

    const klussen = new Set(lijst.map(function (c) { return c.dataset.q; })).size;
    const dagen = new Set(lijst.map(function (c) { return c.dataset.k; })).size;
    const naam = klusVan(lijst[0]).querySelector(".wie").textContent.trim();
    klusVenster.querySelector(".wp-dialoogtitel").textContent =
      (klussen === 1 ? naam : klussen + " klussen") + " · " +
      (dagen === 1 ? datumVan(lijst[0]) : dagen + " dagen");
    klusVenster.querySelector("[data-sub]").textContent = "";

    const gepland = gedeeld(lijst, "gepland");
    kf.querySelectorAll("[name=gepland]").forEach(function (keuze) {
      keuze.checked = gepland !== null && keuze.value === (gepland ? "ja" : "nee");
    });
    // Eén klik op een lege dag is bijna altijd "die wil ik plannen".
    if (gepland === "") kf.querySelector("[name=gepland][value=ja]").checked = true;

    const notitie = gedeeld(lijst, "notitie");
    kf.elements.notitie.value = notitie === null ? "" : notitie;
    kf.elements.notitie_wijzigen.value = notitie === null ? "0" : "1";
    klusVenster.querySelector("[data-notitie-gemengd]").hidden = notitie !== null;
    toonKlusNotitie();
    window.openSheet(klusVenster);
  }

  function toonKlusNotitie() {
    const kf = klusVenster.querySelector("form");
    const keuze = kf.querySelector("[name=gepland]:checked");
    klusVenster.querySelector("[data-klusnotitie-blok]").hidden = !!keuze && keuze.value === "nee";
  }

  if (klusVenster) {
    const kf = klusVenster.querySelector("form");
    kf.addEventListener("change", toonKlusNotitie);
    kf.elements.notitie.addEventListener("input", function () {
      kf.elements.notitie_wijzigen.value = "1";
      klusVenster.querySelector("[data-notitie-gemengd]").hidden = true;
    });
  }

  // Het klussenblok in- en uitklappen met het minteken. Onthouden per
  // browser: wie hem dicht heeft, wil hem morgen ook dicht.
  const inklapSleutel = "werkplanning-klussen-dicht";
  function zetKlussenDicht(dicht) {
    bord.classList.toggle("klussen-dicht", dicht);
    const knop = bord.querySelector("[data-klussen-inklappen]");
    if (knop) {
      knop.textContent = dicht ? "+" : "−";
      knop.setAttribute("aria-expanded", dicht ? "false" : "true");
      knop.title = dicht ? "Klussen uitklappen" : "Klussen inklappen";
      knop.setAttribute("aria-label", knop.title);
    }
    try { localStorage.setItem(inklapSleutel, dicht ? "1" : ""); } catch (fout) { /* dan maar niet onthouden */ }
  }
  try {
    if (localStorage.getItem(inklapSleutel) === "1") zetKlussenDicht(true);
  } catch (fout) { /* open laten */ }

  // De namenkolom inklappen met het pijltje in de hoek: alleen bol of
  // waaier blijft staan. Ook onthouden per browser.
  const namenSleutel = "werkplanning-namen-smal";
  function zetNamenSmal(smal) {
    bord.classList.toggle("namen-smal", smal);
    const knop = bord.querySelector("[data-namen-inklappen]");
    if (knop) {
      knop.textContent = smal ? "›" : "‹";
      knop.setAttribute("aria-expanded", smal ? "false" : "true");
      knop.title = smal ? "Namen uitklappen" : "Namen inklappen";
      knop.setAttribute("aria-label", knop.title);
    }
    try { localStorage.setItem(namenSleutel, smal ? "1" : ""); } catch (fout) { /* dan maar niet onthouden */ }
  }
  try {
    if (localStorage.getItem(namenSleutel) === "1") zetNamenSmal(true);
  } catch (fout) { /* breed laten */ }

  function naarKolom(k, vloeiend) {
    const kop = bord.querySelector('.wp-kop[data-k="' + Math.max(k, 0) + '"]');
    const namen = bord.querySelector(".bord-hoek");
    if (!kop || !namen) return;
    const verschil = kop.getBoundingClientRect().left
      - scroller.getBoundingClientRect().left - namen.offsetWidth;
    scroller.scrollTo({ left: scroller.scrollLeft + verschil, behavior: vloeiend ? "smooth" : "auto" });
  }

  // "Vandaag": staat vandaag op het bord, dan erheen scrollen in plaats van
  // de pagina opnieuw te laden.
  const naarVandaag = document.querySelector("[data-naar-vandaag]");
  if (naarVandaag) {
    naarVandaag.addEventListener("click", function (e) {
      const kop = bord.querySelector(".wp-kop.vandaag");
      if (!kop) return;
      e.preventDefault();
      naarKolom(Number(kop.dataset.k) - 2, true);
    });
  }

  // Zoom: Dag, Week of Maand bepaalt hoe breed een dag is. Het bord blijft
  // het hele jaar; alleen --dag verandert, dus geen herladen. De dag die
  // links in beeld stond, blijft daar staan. Onthouden per browser.
  const ZOOM = { dag: 240, week: 112, maand: 26 };
  const zoomSleutel = "werkplanning-zoom";
  let zoom = "week";
  function zetZoom(nieuw) {
    if (!ZOOM[nieuw]) return;
    const links = Math.round(scroller.scrollLeft / ZOOM[zoom]);
    zoom = nieuw;
    bord.style.setProperty("--dag", ZOOM[zoom] + "px");
    Object.keys(ZOOM).forEach(function (z) {
      bord.classList.toggle("wp-zoom-" + z, z === zoom);
    });
    document.querySelectorAll("[data-zoom]").forEach(function (knop) {
      knop.classList.toggle("actief", knop.dataset.zoom === zoom);
      knop.setAttribute("aria-pressed", knop.dataset.zoom === zoom ? "true" : "false");
    });
    scroller.scrollLeft = links * ZOOM[zoom];
    try { localStorage.setItem(zoomSleutel, zoom); } catch (fout) { /* dan maar niet onthouden */ }
  }
  document.querySelectorAll("[data-zoom]").forEach(function (knop) {
    knop.addEventListener("click", function () { zetZoom(knop.dataset.zoom); });
  });
  try { zetZoom(localStorage.getItem(zoomSleutel) || "week"); } catch (fout) { zetZoom("week"); }

  // Na opslaan laadt de pagina opnieuw. Onthoud waar je stond, anders
  // springt het bord na elke wijziging terug naar boven en naar links.
  const sleutel = "werkplanning-plek";
  document.querySelectorAll(".wp-dialoog form").forEach(function (f) {
    f.addEventListener("submit", function () {
      try {
        sessionStorage.setItem(sleutel, JSON.stringify({
          y: window.scrollY, x: scroller.scrollLeft,
        }));
      } catch (fout) { /* privévenster: dan maar bovenaan */ }
    });
  });
  try {
    const plekOud = JSON.parse(sessionStorage.getItem(sleutel) || "null");
    sessionStorage.removeItem(sleutel);
    if (plekOud) {
      scroller.scrollLeft = plekOud.x;
      window.scrollTo(0, plekOud.y);
      return;
    }
  } catch (fout) { /* niets te herstellen */ }

  // Doorlopend is het hele jaar; open op vandaag (of de gekozen dag), met
  // twee dagen ervoor nog in beeld zodat je ziet waar je vandaan komt.
  naarKolom(Number(bord.dataset.startkolom) - 2);
})();
