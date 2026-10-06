/* Open/sluit-gedrag voor een <dialog> die er op een telefoon als bottom
   sheet uitziet (zie "TELEFOON: BOTTOM SHEET" in app.css, dialog.uren-invoegen).

   showModal()/close() zetten `display` synchroon om — zonder omweg is er
   niets om te animeren, de sheet knalt in of uit beeld.

   Twee paden, bewust naast elkaar:

   - Telefoon, gewone bewegingsinstelling: de sheet wordt in JS gestuurd met
     een veer (static/js/beweging.js). Dat is nodig omdat je hem ook kunt
     slepen: een CSS-transitie kun je niet halverwege beetpakken en
     omdraaien, een veer wel — die rekent altijd verder vanaf de stand die nú
     op het scherm staat.
   - Breed scherm, of "minder beweging" aan: het oude pad met een klasse en
     de CSS-overgang (op breed zonder overgang, dan sluit hij meteen). */
(function () {
  var MOBIEL = "(max-width:700px)";

  function sheetWeergave() {
    return window.matchMedia(MOBIEL).matches;
  }

  /* Mag deze dialoog geveerd en gesleept worden? Alleen als het écht een
     bottom sheet is: smal scherm, gewone bewegingsinstelling, én door CSS
     met een transform van onderen neergezet (zie "TELEFOON: BOTTOM SHEET" in
     app.css). Een gewoon venster in het midden — of dezelfde sheet bij
     "minder beweging", waar de transform wegvalt — zou anders van onderen
     komen inschuiven terwijl het ontwerp dat niet zegt.
     Alleen aanroepen als de dialoog al open is: een transform in procenten
     is op een onzichtbaar element niet betrouwbaar uit te lezen. */
  function sheetGedrag(dialoog) {
    if (!sheetWeergave() || window.Beweging.rustig()) return false;
    var t = window.getComputedStyle(dialoog).transform;
    return !!t && t !== "none";
  }

  // Veert de sheet zelf, dus de CSS-overgang moet er daarbij af: zie
  // dialog.sheet-direct in app.css.
  function zet(dialoog, y) {
    dialoog.style.transform = "translateY(" + y + "px)";
  }

  // Waar staat hij nú? Nodig om een lopende veer te onderbreken zonder
  // zichtbare sprong (en om vanaf een halve sleep verder te sluiten).
  function huidigeY(dialoog) {
    var m = /translateY\((-?[\d.]+)px\)/.exec(dialoog.style.transform || "");
    return m ? parseFloat(m[1]) : 0;
  }

  function hoogteVan(dialoog) {
    return dialoog.offsetHeight || window.innerHeight;
  }

  function stopVeer(dialoog) {
    if (dialoog._sheetVeer) {
      dialoog._sheetVeer.stop();
      dialoog._sheetVeer = null;
    }
  }

  function opgeruimd(dialoog) {
    stopVeer(dialoog);
    dialoog.style.transform = "";
    // Eerst de eindstand laten vastleggen terwijl sheet-direct de CSS-overgang
    // nog uit houdt. Anders ziet de browser bij het weghalen van de klasse de
    // laatste getekende veerstand (een paar px) als vertrekpunt, en neemt de
    // overgang van 0,22 s het laatste stukje over: een naadje in de beweging.
    void dialoog.offsetHeight;
    dialoog.classList.remove("sheet-direct");
  }

  /* Veert naar `naar` (0 = open, hoogte = dicht) vanaf waar hij nu staat, met
     de snelheid waarmee de vinger losliet. Demping 1 als er geen gebaar aan
     voorafging (netjes, geen doorschieten), 0.8 na een worp — dan mag hij een
     tikje doorschieten, want dat deed je hand ook. */
  function veerNaar(dialoog, naar, snelheid, demping) {
    var van = huidigeY(dialoog);
    stopVeer(dialoog);
    dialoog.classList.add("sheet-direct");
    dialoog._sheetVeer = window.Beweging.veer({
      van: van,
      naar: naar,
      snelheid: snelheid || 0,
      demping: demping === undefined ? 1 : demping,
      // Apple's tabel voor een drawer/sheet: respons 0.3.
      respons: 0.3,
      stap: function (y) { zet(dialoog, y); },
      klaar: function () {
        dialoog._sheetVeer = null;
        if (naar === 0) {
          // Open: inline transform weer weg, de klasse houdt hem op zijn plek.
          opgeruimd(dialoog);
        } else {
          dialoog.close();
          dialoog.classList.remove("open-anim");
          opgeruimd(dialoog);
        }
      },
    });
  }

  window.openSheet = function (dialoog) {
    dialoog.showModal();

    if (!sheetGedrag(dialoog)) {
      // Twee frames wachten: het eerste laat de browser de dichte stand
      // (translateY 100%) echt tekenen; pas het tweede mag de overgang naar
      // open in gang zetten. Eén frame is soms te vroeg — dan ziet de browser
      // geen verschil tussen "net getoond" en "open" en slaat de animatie over.
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          dialoog.classList.add("open-anim");
        });
      });
      return;
    }

    // De klasse zet de eindstand (open) vast; de inline transform zet hem
    // eerst nog onder het scherm, waarna de veer hem omhoog brengt. Zonder
    // die klasse zou hij na het opruimen van de inline stand terugvallen op
    // translateY(100%) en weer verdwijnen.
    dialoog.classList.add("open-anim", "sheet-direct");
    zet(dialoog, hoogteVan(dialoog));
    veerNaar(dialoog, 0, 0, 1);
  };

  window.closeSheet = function (dialoog) {
    if (dialoog.open && sheetGedrag(dialoog)) {
      veerNaar(dialoog, hoogteVan(dialoog), 0, 1);
      return;
    }

    dialoog.classList.remove("open-anim");
    // Breed scherm: daar staat geen overgang op de dialoog. Wachten op een
    // transitionend die nooit komt, hield het venster 300 ms open na een klik
    // op het kruisje — precies de soort wachttijd die een tik dood laat
    // aanvoelen. Dus eerst kijken of er wel íets te animeren valt.
    var duur = 0;
    var stijl = window.getComputedStyle(dialoog);
    (stijl.transitionDuration || "").split(",").forEach(function (d) {
      duur = Math.max(duur, parseFloat(d) || 0);
    });
    if (duur === 0) {
      dialoog.close();
      return;
    }

    var klaar = function () {
      dialoog.removeEventListener("transitionend", klaar);
      dialoog.close();
    };
    dialoog.addEventListener("transitionend", klaar);
    // Vangnet: een browser die transitionend om wat voor reden dan ook niet
    // vuurt, mag de dialoog niet voorgoed open laten staan.
    setTimeout(function () {
      if (dialoog.open) {
        dialoog.removeEventListener("transitionend", klaar);
        dialoog.close();
      }
    }, duur * 1000 + 80);
  };

  /* ── Slepen aan het staafje ──────────────────────────────────────────────
     Het staafje bovenaan een sheet is het universele teken "hier kun je aan
     trekken". Dat deed het tot nu toe niet, dus probeerde je het één keer en
     daarna niet meer. Nu volgt de sheet de vinger 1:1 (met weerstand als je
     hém verder omhoog trekt dan hij kan), en bepaalt bij het loslaten de
     snelheid waar hij uitkomt — niet de afstand. Een kort, snel veegje sluit
     dus, langzaam een stuk omlaag trekken en vasthouden niet.

     Gedelegeerd vanaf document: de inhoud van een sheet wordt soms pas later
     van de server gehaald (laadEnOpenSheet hieronder), dus het staafje
     bestaat op dat moment nog niet. */
  var sleep = null;

  document.addEventListener("pointerdown", function (gebeurtenis) {
    if (!gebeurtenis.target.closest) return;
    var hendel = gebeurtenis.target.closest(".sheet-hendel");
    if (!hendel) return;
    var dialoog = hendel.closest("dialog");
    if (!dialoog || !dialoog.open || !sheetGedrag(dialoog)) return;

    // Beetpakken tijdens het openen of sluiten: de veer stopt en we gaan
    // verder vanaf de stand van nu, zodat er niets verspringt.
    stopVeer(dialoog);
    dialoog.classList.add("sheet-direct");

    sleep = {
      dialoog: dialoog,
      vinger: gebeurtenis.pointerId,
      startY: gebeurtenis.clientY,
      // Het grijppunt: niet naar 0 springen, maar verder vanaf waar hij staat.
      grijpY: huidigeY(dialoog),
      hoogte: hoogteVan(dialoog),
      meter: window.Beweging.snelheidsmeter(),
    };
    sleep.meter.voeg(gebeurtenis.clientY, gebeurtenis.timeStamp);
    hendel.setPointerCapture(gebeurtenis.pointerId);
  });

  document.addEventListener("pointermove", function (gebeurtenis) {
    if (!sleep || gebeurtenis.pointerId !== sleep.vinger) return;
    var y = sleep.grijpY + (gebeurtenis.clientY - sleep.startY);
    // Omhoog kan niet verder dan open: daar geeft hij alleen nog mee met
    // toenemende weerstand, in plaats van te blokkeren.
    if (y < 0) y = -window.Beweging.rubberband(-y, sleep.hoogte);
    zet(sleep.dialoog, y);
    sleep.meter.voeg(gebeurtenis.clientY, gebeurtenis.timeStamp);
  });

  function sleepKlaar(gebeurtenis, afgebroken) {
    if (!sleep || gebeurtenis.pointerId !== sleep.vinger) return;
    var dialoog = sleep.dialoog;
    var hoogte = sleep.hoogte;
    var snelheid = afgebroken ? 0 : sleep.meter.snelheid();
    var y = huidigeY(dialoog);
    sleep = null;

    // Niet vanaf waar je losliet beslissen, maar vanaf waar het gebaar heen
    // gaat: zo gooit een flick de sheet weg, ook als je nauwelijks bewoog.
    var projectie = y + window.Beweging.projecteer(snelheid, 0.995);
    if (!afgebroken && projectie > hoogte * 0.32) {
      veerNaar(dialoog, hoogte, snelheid, 1);
    } else {
      // Terug naar open, met de snelheid van de vinger erin: een tikje
      // doorschieten mag hier, er ging een worp aan vooraf.
      veerNaar(dialoog, 0, snelheid, 0.8);
    }
  }

  document.addEventListener("pointerup", function (g) { sleepKlaar(g, false); });
  document.addEventListener("pointercancel", function (g) { sleepKlaar(g, true); });

  /* innerHTML voert geen <script>-tags uit die erin zitten (o.a. de foto-popup
     in _fotoraster.html heeft die nodig) — daarom worden ze hier één voor één
     vervangen door een vers <script>-element, dat de browser wél uitvoert.
     Gebruikt door laadEnOpenSheet hieronder en door het formulier zelf als het
     ná een mislukte post opnieuw in de sheet wordt gezet (zie
     uren/_uurblokformulier.html). */
  window.voerScriptsUit = function (element) {
    element.querySelectorAll("script").forEach(function (oud) {
      const nieuw = document.createElement("script");
      for (let i = 0; i < oud.attributes.length; i++) {
        nieuw.setAttribute(oud.attributes[i].name, oud.attributes[i].value);
      }
      nieuw.textContent = oud.textContent;
      oud.replaceWith(nieuw);
    });
  };

  /* Vult een lege <dialog> met HTML die van de server wordt opgehaald en opent
      'm daarna als sheet — voor schermen die bestaande content tonen (zoals het
     uurblok-detail vanuit de agenda) in plaats van een leeg formulier dat er al
     in de pagina stond. Bij een netwerkfout valt dit terug op gewoon navigeren
     naar `terugvalHref`, zodat de link ook zonder JS/fetch blijft werken. */
  window.laadEnOpenSheet = function (dialoog, url, terugvalHref) {
    fetch(url)
      .then(function (respons) {
        if (!respons.ok) throw new Error("laden mislukt: " + respons.status);
        return respons.text();
      })
      .then(function (html) {
        dialoog.innerHTML = html;
        // Het fragment weet niet op welk scherm het staat: zijn "terug" is
        // het adres van het fragment zelf. Na een upload zou je dan op een
        // kaal stuk HTML belanden. Daarom hier het echte scherm invullen, en
        // links die de weg terug meenemen (data-met-terug) ook.
        var hier = window.location.pathname + window.location.search;
        dialoog.querySelectorAll('input[name="terug"]').forEach(function (veld) {
          veld.value = hier;
        });
        dialoog.querySelectorAll("a[data-met-terug]").forEach(function (link) {
          link.href += (link.href.indexOf("?") === -1 ? "?" : "&") + "terug=" + encodeURIComponent(hier);
        });
        window.voerScriptsUit(dialoog);
        window.openSheet(dialoog);
      })
      .catch(function () {
        window.location.href = terugvalHref;
      });
  };
})();
