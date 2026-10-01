/* Werkplanning (templates/uren/aanwezigheid.html): cellen kiezen en zetten.

   Kiezen gaat zoals in Excel:
   - klik op een cel: die ene cel
   - slepen: een blok van de eerste tot de laatste cel (meer dagen, meer mensen)
   - shift-klik: een blok van de vorige cel tot deze
   - klik op een naam: al zijn dagen; klik op een dag: iedereen op die dag
   Daarna gaat het venster open en zet één formulier de hele selectie.
   Cellen van iemand die op die dag niet in dienst is, doen niet mee.

   Op een aanraakscherm schuift slepen het bord opzij in plaats van te
   kiezen; daar kiest een tik alleen die ene cel. Daar is dit scherm ook
   niet voor gemaakt. */
(function () {
  const bord = document.getElementById("wp-bord");
  const venster = document.getElementById("wp-cellen");
  const notitieVenster = document.getElementById("wp-notitie");
  if (!bord || !venster) return;

  const cellen = Array.from(bord.querySelectorAll("button.wp-cel"));
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

  function plek(cel) {
    return { r: Number(cel.dataset.r), k: Number(cel.dataset.k) };
  }

  function blok(van, tot) {
    const a = plek(van), b = plek(tot);
    const r1 = Math.min(a.r, b.r), r2 = Math.max(a.r, b.r);
    const k1 = Math.min(a.k, b.k), k2 = Math.max(a.k, b.k);
    return cellen.filter(function (cel) {
      const p = plek(cel);
      return p.r >= r1 && p.r <= r2 && p.k >= k1 && p.k <= k2;
    });
  }

  function markeer(gekozen) {
    cellen.forEach(function (cel) { cel.classList.remove("gekozen"); });
    gekozen.forEach(function (cel) { cel.classList.add("gekozen"); });
  }

  function gekozen() {
    return cellen.filter(function (cel) { return cel.classList.contains("gekozen"); });
  }

  // Eén waarde als alle gekozen cellen hem delen, anders null: dan staat er
  // in het venster niets voorgekozen en zet je bewust iets nieuws.
  function gedeeld(lijst, sleutel) {
    const eerste = lijst[0].dataset[sleutel];
    return lijst.every(function (cel) { return cel.dataset[sleutel] === eerste; }) ? eerste : null;
  }

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
    // "Volgens rooster" haalt de afwijking weg, opmerking en al.
    opmerking.closest("[data-opmerking-blok]").hidden = !!stand && stand.value === "standaard";
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
      titel.textContent = lijst[0].title.split(" · ").slice(0, 2).join(" · ");
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
    const cel = e.target.closest("button.wp-cel");
    if (!cel || e.button !== 0) return;
    e.preventDefault();   // geen tekst selecteren tijdens het slepen
    if (e.shiftKey && anker) {
      markeer(blok(anker, cel));
    } else {
      anker = cel;
      markeer([cel]);
    }
    sleept = true;
  });

  bord.addEventListener("mouseover", function (e) {
    if (!sleept) return;
    const cel = e.target.closest("button.wp-cel");
    if (cel) markeer(blok(anker, cel));
  });

  document.addEventListener("mouseup", function () {
    if (!sleept) return;
    sleept = false;
    openVenster(gekozen());
  });

  // Toetsenbord en aanraken: een "click" zonder voorafgaande mousedown.
  bord.addEventListener("click", function (e) {
    const cel = e.target.closest("button.wp-cel");
    if (cel && e.detail === 0) {
      anker = cel;
      openVenster([cel]);
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

  [venster, notitieVenster].forEach(function (dialoog) {
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

  // Na opslaan laadt de pagina opnieuw. Onthoud waar je stond, anders
  // springt het bord na elke wijziging terug naar boven en naar links.
  const scroller = bord.closest(".wp-scroll");
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
    }
  } catch (fout) { /* niets te herstellen */ }
})();
