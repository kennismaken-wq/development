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

    let vasthoudTimer = null;
    let vingerId = null;
    let startX = null, startY = null;

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

      // Vinger: nog niets blokkeren, anders kan er ook niet meer gescrold
      // worden zolang we niet zeker weten dat dit een vasthouden wordt.
      if (vingerId !== null) return;   // al een andere vinger aan het volgen
      const vak = gebeurtenis.target.closest(".vak");
      if (!vak) return;
      vingerId = gebeurtenis.pointerId;
      startX = gebeurtenis.clientX;
      startY = gebeurtenis.clientY;
      const startVak = Number(vak.dataset.vak);
      wisVasthoudTimer();
      vasthoudTimer = setTimeout(function () {
        vasthoudTimer = null;
        van = tot = startVak;
        verf();
        if (navigator.vibrate) navigator.vibrate(10);   // voelbare bevestiging dat slepen nu kan
      }, VASTHOUD_MS);
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

      if (vasthoudTimer !== null) {
        // Nog aan het wachten: bij genoeg beweging is dit een swipe/scroll,
        // geen vasthouden — dan laten we het gewoon aan de browser over.
        const dx = gebeurtenis.clientX - startX;
        const dy = gebeurtenis.clientY - startY;
        if (Math.abs(dx) > BEWEEG_DREMPEL || Math.abs(dy) > BEWEEG_DREMPEL) {
          wisVasthoudTimer();
          vingerId = null;
        }
        return;
      }

      if (van === null) return;   // vasthouden is nooit bevestigd
      gebeurtenis.preventDefault();   // vanaf hier geen paginascroll meer
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
      vingerId = null;
      if (van === null) return;   // gewone tik: dat handelt de click-listener hieronder af
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
})();
