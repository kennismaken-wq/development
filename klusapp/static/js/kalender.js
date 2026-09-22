/* Slepen in de weekkalender.

   Met een muis sleep je meteen over de halfuurvakken en laat je los. Met een
   vinger kan dat niet meteen: een sleepbeweging is dan niet te onderscheiden
   van scrollen. Daarom eerst even vasthouden (net als Google Calendar) — pas
   ná die korte vertraging blokkeert het gebaar de paginascroll en kun je
   verticaal slepen om een tijdvak te tekenen. Een gewone, korte tik blijft
   gewoon het formulier openen met alleen een begintijd. */
(function () {
  const script = document.currentScript;
  const nieuwUrl = script.dataset.nieuwUrl;

  const START_MIN = 6 * 60;
  const VAK_MIN = 30;

  function tijd(vaknummer) {
    const minuut = START_MIN + vaknummer * VAK_MIN;
    return String(Math.floor(minuut / 60)).padStart(2, "0") + ":" +
           String(minuut % 60).padStart(2, "0");
  }

  function openFormulier(dag, vanVak, totVak) {
    // totVak is null bij een tik: dan alleen een begintijd meegeven.
    const van = totVak === null ? vanVak : Math.min(vanVak, totVak);
    const vanTijd = tijd(van);
    const totTijd = totVak === null ? "" : tijd(Math.max(vanVak, totVak) + 1);

    // De dialoog staat al klaar in de pagina (mijn_uren.html): die vullen we
    // met de gesleepte dag/tijd en openen we, in plaats van ernaartoe te
    // navigeren — zo blijft de agenda op de achtergrond zichtbaar. Alleen in
    // de maandweergave staat de dialoog er niet (geen sleepbaar raster), dan
    // valt dit terug op de oude navigatie.
    const dialoog = document.getElementById("uren-invoegen");
    if (!dialoog) {
      let adres = nieuwUrl + "?dag=" + dag + "&van=" + vanTijd;
      if (totTijd) adres += "&tot=" + totTijd;
      window.location.href = adres;
      return;
    }
    dialoog.querySelector("form").action = nieuwUrl + "?dag=" + dag;
    document.getElementById("id_datum").value = dag;
    document.getElementById("id_begintijd").value = vanTijd;
    document.getElementById("id_eindtijd").value = totTijd;
    window.openSheet(dialoog);
  }

  let muisGebruikt = false;

  // Swipe tussen dagen — alleen in de dagweergave (precies één kolom): de
  // weekweergave scrollt zelf al horizontaal tussen de zeven kolommen, en
  // swipe-navigatie zou daarmee vechten om dezelfde vingerbeweging.
  const dagkolommen = document.querySelectorAll(".raster.raster-dag .dagkolom");
  if (dagkolommen.length === 1) {
    const kolom = dagkolommen[0];
    const vorigeLink = document.querySelector('[data-urennav="vorige"]');
    const volgendeLink = document.querySelector('[data-urennav="volgende"]');
    if (vorigeLink && volgendeLink) {
      const DREMPEL = 55; // px, moet overduidelijk een swipe zijn en geen trillende tik
      let startX = null, startY = null, aanHetSwipen = false;

      kolom.addEventListener("pointerdown", function (gebeurtenis) {
        if (gebeurtenis.pointerType === "mouse") return;
        startX = gebeurtenis.clientX;
        startY = gebeurtenis.clientY;
        aanHetSwipen = false;
      });
      kolom.addEventListener("pointermove", function (gebeurtenis) {
        if (startX === null || gebeurtenis.pointerType === "mouse") return;
        const dx = gebeurtenis.clientX - startX;
        const dy = gebeurtenis.clientY - startY;
        if (!aanHetSwipen && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy)) {
          aanHetSwipen = true;
        }
      });
      kolom.addEventListener("pointerup", function (gebeurtenis) {
        if (startX === null || gebeurtenis.pointerType === "mouse") return;
        const dx = gebeurtenis.clientX - startX;
        startX = null;
        if (!aanHetSwipen || Math.abs(dx) < DREMPEL) return;
        // Swipe naar links = volgende dag (bladeren naar voren), naar rechts
        // = vorige dag — dezelfde richting als een agenda-app op een telefoon.
        window.location.href = (dx < 0 ? volgendeLink : vorigeLink).href;
      });
      // Voorkomt dat de gewone tik-opent-formulier-handler hieronder ook nog
      // afgaat ná een swipe: die luistert naar "click", en pointerup ligt
      // daar altijd vóór. window.location.href hierboven zet de navigatie al
      // in gang, maar de klik zou daarvóór nog even het formulier kunnen
      // laten opflitsen.
      kolom.addEventListener(
        "click",
        function (gebeurtenis) {
          if (aanHetSwipen) {
            gebeurtenis.stopImmediatePropagation();
            gebeurtenis.preventDefault();
          }
        },
        true
      );
    }
  }

  const VASTHOUD_MS = 450;       // ms stilhouden voordat een vinger mag slepen
  const BEWEEG_DREMPEL = 10;     // px — hierboven is het een swipe, geen vasthouden

  document.querySelectorAll(".dagkolom").forEach(function (kolom) {
    let van = null, tot = null;
    let langePersAfgehandeld = false;

    // touch-action op de kolom staat vast op "none" (zie app.css): Chromium
    // bepaalt bij het begin van een aanraking eens en voor altijd of hij zelf
    // mag scrollen, en negeert latere CSS- of pointer-capture-wijzigingen
    // (uitgeprobeerd — geen van beide werkte om een al lopend sleepgebaar
    // alsnog te blokkeren). Daarom scrollen we een gewone swipe hieronder
    // zelf na (modus "scrollen"), i.p.v. dat aan de browser over te laten.
    let vasthoudTimer = null;
    let vingerId = null;
    let modus = null;   // "wachten" | "kiezen" | "scrollen" — alleen tijdens een vingergebaar
    let startX = null, startY = null, laatsteX = null, laatsteY = null;
    let horizontaleScroller = null;
    let verticaleScroller = null;

    // html,body staan op height:100% (zie app.css), waardoor niet het venster
    // maar <body> zelf de scrollende doos is (window.scrollY blijft dan altijd
    // 0). Zoek daarom het element dat écht overloopt i.p.v. domweg window aan
    // te nemen — anders scrolt een gewone swipe straks nergens naartoe.
    function zoekVerticaleScroller() {
      const el = document.scrollingElement;
      if (el && el.scrollHeight > el.clientHeight) return el;
      return document.body;
    }

    function verf() {
      kolom.querySelectorAll(".vak").forEach(function (vak) {
        const index = Number(vak.dataset.vak);
        const binnen = van !== null && index >= Math.min(van, tot) && index <= Math.max(van, tot);
        vak.classList.toggle("kiezen", binnen);
      });
    }

    function wis() {
      van = tot = null;
      kolom.querySelectorAll(".vak").forEach(function (vak) {
        vak.classList.remove("kiezen");
      });
    }

    function wisVasthoudTimer() {
      if (vasthoudTimer !== null) {
        clearTimeout(vasthoudTimer);
        vasthoudTimer = null;
      }
    }

    // Zoekt het vak onder een schermpositie, ongeacht welk element de vinger
    // ooit als target had — bij een vinger blijft event.target namelijk
    // "vastgeplakt" aan het vak van de eerste aanraking (impliciete pointer
    // capture), terwijl de muis dat gewoon bijwerkt via closest() hieronder.
    function vakOpPositie(x, y) {
      const el = document.elementFromPoint(x, y);
      const vak = el && el.closest(".vak");
      return vak && vak.closest(".dagkolom") === kolom ? vak : null;
    }

    kolom.addEventListener("pointerdown", function (gebeurtenis) {
      if (gebeurtenis.pointerType === "mouse") {
        muisGebruikt = true;
        const vak = gebeurtenis.target.closest(".vak");
        if (!vak) return;
        van = tot = Number(vak.dataset.vak);
        verf();
        return;
      }

      if (vingerId !== null) return;   // al een andere vinger aan het volgen
      vingerId = gebeurtenis.pointerId;
      startX = laatsteX = gebeurtenis.clientX;
      startY = laatsteY = gebeurtenis.clientY;
      modus = "wachten";
      horizontaleScroller = kolom.closest(".raster-scroll");
      verticaleScroller = zoekVerticaleScroller();

      // Alleen op een leeg vak mag vasthouden een sleep beginnen; op een
      // bestaand blok (een link naar een uurblok) blijft dit gewoon een tik
      // of — als er toch bewogen wordt — een scroll, zie pointermove.
      const vak = gebeurtenis.target.closest(".vak");
      if (vak) {
        const startVak = Number(vak.dataset.vak);
        wisVasthoudTimer();
        vasthoudTimer = setTimeout(function () {
          vasthoudTimer = null;
          modus = "kiezen";
          van = tot = startVak;
          verf();
          if (navigator.vibrate) navigator.vibrate(10);   // voelbare bevestiging dat slepen nu kan
        }, VASTHOUD_MS);
      }
    });

    kolom.addEventListener("pointermove", function (gebeurtenis) {
      if (gebeurtenis.pointerType === "mouse") {
        if (van === null) return;
        const vak = gebeurtenis.target.closest(".vak");
        if (!vak) return;
        tot = Number(vak.dataset.vak);
        verf();
        return;
      }

      if (gebeurtenis.pointerId !== vingerId) return;

      const dx = gebeurtenis.clientX - laatsteX;
      const dy = gebeurtenis.clientY - laatsteY;
      laatsteX = gebeurtenis.clientX;
      laatsteY = gebeurtenis.clientY;

      if (modus === "wachten") {
        const totaalDx = gebeurtenis.clientX - startX;
        const totaalDy = gebeurtenis.clientY - startY;
        if (Math.abs(totaalDx) <= BEWEEG_DREMPEL && Math.abs(totaalDy) <= BEWEEG_DREMPEL) {
          return;   // nog te weinig beweging om te weten wat dit wordt
        }
        // Genoeg beweging vóór het vasthouden bevestigd was: gewone swipe.
        wisVasthoudTimer();
        modus = "scrollen";
        // Bewust doorvallen naar hieronder: anders gaat deze eerste,
        // drempeloverschrijdende beweging verloren.
      }

      if (modus === "scrollen") {
        verticaleScroller.scrollTop -= dy;
        if (horizontaleScroller) horizontaleScroller.scrollLeft -= dx;
        return;
      }

      // modus === "kiezen"
      const vak = vakOpPositie(gebeurtenis.clientX, gebeurtenis.clientY);
      if (vak) {
        tot = Number(vak.dataset.vak);
        verf();
      }
    });

    kolom.addEventListener("pointerup", function (gebeurtenis) {
      if (gebeurtenis.pointerType === "mouse") {
        if (van === null) return;
        const vanVak = van, totVak = tot;
        wis();
        openFormulier(kolom.dataset.dag, vanVak, totVak);
        return;
      }

      if (gebeurtenis.pointerId !== vingerId) return;
      wisVasthoudTimer();
      const eindeModus = modus;
      vingerId = null;
      modus = null;
      if (eindeModus !== "kiezen") return;   // gewone tik of scroll: click-listener/browser regelt de rest
      const vanVak = van, totVak = tot;
      wis();
      langePersAfgehandeld = true;   // voorkomt dat de click hieronder het formulier nog eens opent
      openFormulier(kolom.dataset.dag, vanVak, totVak);
    });

    kolom.addEventListener("pointercancel", function (gebeurtenis) {
      if (gebeurtenis.pointerType === "mouse") {
        wis();
        return;
      }
      if (gebeurtenis.pointerId !== vingerId) return;
      wisVasthoudTimer();
      vingerId = null;
      modus = null;
      wis();
    });

    // Alleen relevant voor de muis: een vinger "verlaat" het vak tijdens het
    // slepen niet op dezelfde manier (impliciete pointer capture), dus die
    // zou hier onterecht de selectie wissen.
    kolom.addEventListener("pointerleave", function (gebeurtenis) {
      if (gebeurtenis.pointerType === "mouse") wis();
    });

    // Op een aanraakscherm: een korte tik (geen vasthouden) opent het
    // formulier met dat halfuur als begintijd; na een sleep heeft pointerup
    // hierboven dat al gedaan.
    kolom.addEventListener("click", function (gebeurtenis) {
      if (langePersAfgehandeld) {
        langePersAfgehandeld = false;
        return;
      }
      if (muisGebruikt) return;   // de muis heeft het al via pointerup gedaan
      const vak = gebeurtenis.target.closest(".vak");
      if (!vak) return;
      openFormulier(kolom.dataset.dag, Number(vak.dataset.vak), null);
    });
  });

  // Klik op een bestaand blok: het detail als sheet tonen (net als "uren
  // toevoegen") in plaats van naar uurblok_detail te navigeren. Alleen de
  // gewone, ongewijzigde klik onderscheppen we — ctrl/cmd/shift/middelste
  // knop laten we intact, zodat "open in nieuw tabblad" e.d. blijft werken.
  const detailDialoog = document.getElementById("uurblok-detail");
  if (detailDialoog) {
    document.querySelectorAll("a.blok[data-paneel-url]").forEach(function (blok) {
      blok.addEventListener("click", function (gebeurtenis) {
        if (gebeurtenis.defaultPrevented || gebeurtenis.button !== 0 ||
            gebeurtenis.metaKey || gebeurtenis.ctrlKey || gebeurtenis.shiftKey || gebeurtenis.altKey) {
          return;
        }
        gebeurtenis.preventDefault();
        window.laadEnOpenSheet(detailDialoog, blok.dataset.paneelUrl, blok.href);
      });
    });
  }
})();
