/* Gedeelde bewegingshulpjes: één veer, één projectie, één rubberband.

   Waarom één bestand en niet per script een eigen versie: een sheet die
   wegveert en een dagweergave waar je naar links veegt moeten hetzelfde
   aanvoelen, en dat lukt alleen als ze dezelfde rekenregels gebruiken. Geen
   bibliotheek: dit zijn dertig regels rekenwerk op requestAnimationFrame.

   Dit script staat in basis.html vóór de rest, zodat elk scherm (en elk
   fragment dat later in een <dialog> wordt gezet) erover kan beschikken. */
(function () {
  /* Wil de gebruiker zo weinig beweging mogelijk? Dan geen veren en geen
     schuiven; de aanroeper valt in dat geval terug op een rustige
     overvloeier in CSS. Elke keer opnieuw opvragen i.p.v. één keer bij het
     laden: de instelling kan tijdens een sessie wijzigen. */
  function rustig() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /* Waar komt iets uit als je het met deze snelheid loslaat? Dit is de
     formule uit Apple's "Designing Fluid Interfaces" (exponentieel
     uitdempen, zoals scrollen), niet de natuurkundeboek-variant
     v²/(2a) — die projecteert veel te kort en dan voelt een snelle veeg
     alsof hij niet is aangekomen.

     snelheid in px/s; remfactor 0.998 is gewoon scrollgevoel, lager is
     korter/kordater. */
  function projecteer(snelheid, remfactor) {
    var d = remfactor === undefined ? 0.998 : remfactor;
    return (snelheid / 1000) * d / (1 - d);
  }

  /* Weerstand voorbij een rand: hoe verder je trekt, hoe minder het meegeeft.
     Een harde stop leest als "vastgelopen", dit als "het kan wel, maar er is
     niets meer". `over` is hoeveel px je voorbij de rand zit, `maat` de maat
     van het ding dat je sleept. */
  function rubberband(over, maat, constante) {
    var c = constante === undefined ? 0.55 : constante;
    return (over * maat * c) / (maat + c * Math.abs(over));
  }

  /* Veer van `van` naar `naar`, eventueel met de snelheid waarmee de vinger
     losliet. Twee knoppen, zoals Apple ze aan ontwerpers geeft:

     - demping: 1 = kritisch gedempt, komt netjes tot stilstand zonder
       doorschieten. Lager (0.8) schiet een beetje door — alleen gebruiken als
       er een worp aan voorafging, anders voelt het slap.
     - respons: hoe snel hij er is, in seconden. Dit is géén looptijd: een
       veer heeft geen vaste duur, die volgt uit de parameters.

     Onderbreekbaar: `stop()` zet hem stil, en `waarde`/`snelheid` geven de
     stand van nú — zo begint een nieuw gebaar bij wat er op het scherm staat
     in plaats van bij het doel, wat anders een zichtbare sprong geeft. */
  function veer(opties) {
    var waarde = opties.van;
    var snelheid = opties.snelheid || 0;
    var doel = opties.naar;
    var demping = opties.demping === undefined ? 1 : opties.demping;
    var respons = opties.respons === undefined ? 0.35 : opties.respons;
    // Omrekening van (demping, respons) naar stijfheid/wrijving van een
    // massa-1-veer; respons is de trillingstijd, dus 2π/respons.
    var stijfheid = Math.pow((2 * Math.PI) / respons, 2);
    var wrijving = (4 * Math.PI * demping) / respons;
    var vorigeTijd = null;
    var bezig = true;
    var id = null;

    function stap(nu) {
      if (!bezig) return;
      if (vorigeTijd === null) vorigeTijd = nu;
      // Na een hik (tab op de achtergrond, trage frame) niet in één enorme
      // sprong doorrekenen: dan klapt de veer over zijn doel heen.
      var dt = Math.min((nu - vorigeTijd) / 1000, 1 / 30);
      vorigeTijd = nu;
      // In kleine stapjes integreren: één stap van 33 ms met deze stijfheid
      // is numeriek niet stabiel.
      var stappen = Math.max(1, Math.ceil(dt / 0.004));
      var h = dt / stappen;
      for (var i = 0; i < stappen; i++) {
        var kracht = -stijfheid * (waarde - doel) - wrijving * snelheid;
        snelheid += kracht * h;
        waarde += snelheid * h;
      }
      opties.stap(waarde, snelheid);
      // Binnen een halve pixel en bijna stil: klaar. Doorrekenen tot exact nul
      // kost frames die niemand ziet.
      if (Math.abs(waarde - doel) < 0.5 && Math.abs(snelheid) < 20) {
        bezig = false;
        waarde = doel;
        snelheid = 0;
        opties.stap(doel, 0);
        if (opties.klaar) opties.klaar();
        return;
      }
      id = requestAnimationFrame(stap);
    }

    id = requestAnimationFrame(stap);

    return {
      stop: function () {
        bezig = false;
        if (id !== null) cancelAnimationFrame(id);
      },
      loopt: function () { return bezig; },
      nu: function () { return waarde; },
      nuSnelheid: function () { return snelheid; },
    };
  }

  /* Snelheid uit de laatste paar pointermove-gebeurtenissen, niet uit het
     verschil tussen begin en eind: een gebaar dat halverwege stilvalt moet
     ook als "losgelaten zonder snelheid" aankomen. */
  function snelheidsmeter() {
    var punten = [];
    return {
      voeg: function (positie, tijd) {
        punten.push({ p: positie, t: tijd });
        // ~100 ms geschiedenis is genoeg en volgt een richtingswissel snel
        while (punten.length > 2 && tijd - punten[0].t > 100) punten.shift();
      },
      snelheid: function () {
        if (punten.length < 2) return 0;
        var eerste = punten[0];
        var laatste = punten[punten.length - 1];
        var dt = laatste.t - eerste.t;
        if (dt <= 0) return 0;
        return ((laatste.p - eerste.p) / dt) * 1000;
      },
      leeg: function () { punten = []; },
    };
  }

  window.Beweging = {
    rustig: rustig,
    projecteer: projecteer,
    rubberband: rubberband,
    veer: veer,
    snelheidsmeter: snelheidsmeter,
  };
})();
