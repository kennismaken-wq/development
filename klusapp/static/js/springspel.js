/* Het springspel: een hovenier springt omhoog over heggen (offerte 2026-O01).

   Twee helften. maakWereld is de spelregels zonder scherm, zodat die ook los
   te controleren zijn; daaronder staat wat tekent, luistert en de score
   verstuurt.

   Afmetingen in "eenheden": het speelveld is altijd 360 breed, de hoogte
   volgt uit het scherm. y loopt omhoog. De regels rekenen in vaste stappen
   van 1/120 s, zodat het spel op een 60 Hz- en een 120 Hz-telefoon even snel
   gaat. */
(function () {
  var BREEDTE = 360;
  var STAP = 1 / 120;
  var ZWAARTEKRACHT = 836;
  var SPRONG = 591;            /* sprong van 209 eenheden hoog */
  var BOOST = 1122;            /* spel/views.py rekent hiermee: MAX_PUNTEN_PER_SECONDE */
  var EENHEDEN_PER_PUNT = 4;
  var LOOPSNELHEID = 270;
  var VERSNELLING = 1700;
  var HALF_VOET = 13;
  var WESP_STRAAL = 13;
  var SPELER_STRAAL = 12;
  /* Zover boven beeld bestaat alles al, zodat een wesp ruim van tevoren met
     een uitroepteken aangekondigd kan worden. */
  var VOORUIT = 700;
  var BLAAS_SNELHEID = 790;    /* blijft onder de boost, zie spel/views.py */
  var BLAAS_DUUR = 2.5;
  var VEILIG_NA_PAK = 1.2;
  var VEILIG_NA_BLAZER = 0.8;
  var OPPAK_STRAAL = 30;

  function tussen(a, b, d) { return a + (b - a) * d; }

  function maakWereld(hoogte, kans) {
    var w = {
      hoogte: hoogte,
      cam: 0,
      punten: 0,
      tijd: 0,
      afgelopen: false,
      platforms: [],
      wespen: [],
      items: [],
      effecten: [],
      speler: { x: BREEDTE / 2, y: 30, vx: 0, vy: SPRONG, kijk: 1, rek: 0, dood: false, pak: false, blazer: 0, veilig: 0 },
    };
    var volgendeY = 110;                 /* de eerste heggen boven de tuin */
    var laatsteWesp = 0;
    var laatsteItem = 0;
    var laatsteBlazer = -6000;           /* de eerste kan vanaf hoogte 3000 */

    w.platforms.push({ soort: "gras", x: BREEDTE / 2, y: 30, b: BREEDTE, vx: 0 });

    function plaats(soort, y, b) {
      var marge = b / 2 + 6;
      var p = { soort: soort, x: marge + kans() * (BREEDTE - 2 * marge), y: y, b: b, vx: 0 };
      w.platforms.push(p);
      return p;
    }

    /* Extra platforms mogen niet over een ander heen vallen: een bladerhoop
       op een heg lees je niet meer. Is er geen plek, dan vervalt deze. */
    function plaatsVrij(soort, y, b) {
      var marge = b / 2 + 6;
      function vrij(x) {
        return w.platforms.every(function (q) {
          return Math.abs(q.y - y) > 38 || (!q.vx && Math.abs(q.x - x) > (q.b + b) / 2 + 6);
        });
      }
      for (var poging = 0; poging < 6; poging++) {
        var x = marge + kans() * (BREEDTE - 2 * marge);
        if (vrij(x)) {
          w.platforms.push({ soort: soort, x: x, y: y, b: b, vx: 0 });
          return;
        }
      }
    }

    function genereer() {
      while (volgendeY < w.cam + w.hoogte + VOORUIT) {
        var d = Math.min(1, volgendeY / 14000);
        /* De keten van vaste platforms: de grootste afstand (162) blijft
           onder de sprong, dus er is altijd een weg omhoog. */
        var afstand = tussen(56, 100, d) + kans() * tussen(30, 62, d);
        var y = volgendeY + afstand;
        volgendeY = y;

        var p;
        if (kans() < tussen(0.05, 0.45, d)) {
          p = plaats("kruiwagen", y, 76);
          p.vx = (kans() < 0.5 ? -1 : 1) * tussen(40, 105, d);
        } else {
          p = plaats("heg", y, tussen(78, 58, d));
          if (y > 1500 && kans() < 0.045) p.boost = (kans() - 0.5) * (p.b - 24);
          if (p.boost === undefined && y > 1200 && y - laatsteItem > 1800 && kans() < 0.12) {
            /* Het imkerpak pas als de bijen bijna komen; eerder heb je er niets aan. */
            var soort = y > 4500 && kans() < 0.5 ? "imkerpak" : "bladblazer";
            if (soort === "imkerpak" || y - laatsteBlazer > 9000) {
              laatsteItem = y;
              if (soort === "bladblazer") laatsteBlazer = y;
              w.items.push({ soort: soort, x: p.x, y: y + 34 });
            }
          }
        }
        if (kans() < tussen(0.55, 0.12, d)) plaatsVrij("heg", y - afstand / 2, tussen(78, 58, d));
        if (kans() < tussen(0.1, 0.3, d)) plaatsVrij("bladerhoop", y - afstand * 0.4, 72);
        if (y > 6000 && y - laatsteWesp > 700 && kans() < tussen(0.12, 0.3, d)) {
          laatsteWesp = y;
          w.wespen.push({ basis: 40 + kans() * (BREEDTE - 80), x: 0, y: y + 30, fase: kans() * 6.28 });
        }
      }
    }

    function raakPlatform(s, oudeY) {
      for (var i = 0; i < w.platforms.length; i++) {
        var p = w.platforms[i];
        if (p.gebroken || oudeY < p.y || s.y > p.y) continue;
        if (Math.abs(s.x - p.x) > p.b / 2 + HALF_VOET) continue;
        if (p.soort === "bladerhoop") {
          p.gebroken = true;
          p.val = 0;
          w.effecten.push({ soort: "breek", x: p.x, y: p.y });
          continue;
        }
        var boost = p.boost !== undefined && Math.abs(s.x - (p.x + p.boost)) < 22;
        s.vy = boost ? BOOST : SPRONG;
        s.y = p.y;
        s.rek = 1;
        w.effecten.push({ soort: boost ? "boost" : "land", x: s.x, y: p.y });
        return;
      }
    }

    function raakWesp(s) {
      for (var i = w.wespen.length - 1; i >= 0; i--) {
        var wesp = w.wespen[i];
        var dx = s.x - wesp.x;
        var dy = s.y + 20 - wesp.y;
        var raakt = dx * dx + dy * dy <= (WESP_STRAAL + SPELER_STRAAL) * (WESP_STRAAL + SPELER_STRAAL);
        /* Vallend met je voeten op of net boven de wesp telt als erop
           springen, ook als je er wat schuin op aankomt. */
        var bovenop = s.vy < 0 && Math.abs(dx) < WESP_STRAAL + HALF_VOET + 8 && s.y > wesp.y - 10 && s.y < wesp.y + 24;
        if (!raakt && !bovenop) continue;
        if (s.vy > SPRONG) continue;              /* in volle boost vlieg je er dwars doorheen */
        if (s.veilig > 0 && !bovenop) continue;
        if (bovenop || (s.vy < 0 && dy > -8)) {
          w.wespen.splice(i, 1);
          s.vy = SPRONG;
          s.rek = 1;
          w.effecten.push({ soort: "plet", x: wesp.x, y: wesp.y });
        } else if (s.pak) {
          /* Het imkerpak vangt één steek op en is dan op. */
          s.pak = false;
          s.veilig = VEILIG_NA_PAK;
          w.wespen.splice(i, 1);
          w.effecten.push({ soort: "plet", x: wesp.x, y: wesp.y });
        } else {
          s.dood = true;
          s.doodOp = w.tijd;
          s.vx *= 0.2;
          s.vy = Math.min(s.vy, -200);
          w.effecten.push({ soort: "steek", x: (s.x + wesp.x) / 2, y: (s.y + 20 + wesp.y) / 2 });
        }
        return;
      }
    }

    function raakItem(s) {
      for (var i = w.items.length - 1; i >= 0; i--) {
        var item = w.items[i];
        var dx = s.x - item.x;
        var dy = s.y + 20 - item.y;
        if (dx * dx + dy * dy > OPPAK_STRAAL * OPPAK_STRAAL) continue;
        if (item.soort === "imkerpak") {
          if (s.pak) continue;                    /* je hebt er al een aan */
          s.pak = true;
        } else {
          s.blazer = BLAAS_DUUR;
        }
        w.items.splice(i, 1);
        w.effecten.push({ soort: "oppak", x: item.x, y: item.y });
        return;
      }
    }

    /* Eén stap van 1/120 s. richting: -1 links, 1 rechts, 0 niets; kantelen
       geeft alles daartussen. */
    w.stap = function (richting) {
      var s = w.speler;
      w.tijd += STAP;

      if (!s.dood) {
        var doel = richting * LOOPSNELHEID;
        var delta = VERSNELLING * STAP;
        s.vx = s.vx < doel ? Math.min(doel, s.vx + delta) : Math.max(doel, s.vx - delta);
        if (richting) s.kijk = richting > 0 ? 1 : -1;
      }
      s.veilig = Math.max(0, s.veilig - STAP);
      if (s.blazer > 0) {
        s.blazer -= STAP;
        s.vy = BLAAS_SNELHEID;
        if (s.blazer <= 0) {
          s.blazer = 0;
          s.vy = SPRONG;
          s.veilig = VEILIG_NA_BLAZER;
        }
      } else {
        s.vy = Math.max(s.vy - ZWAARTEKRACHT * STAP, -823);
      }
      s.rek = Math.max(0, s.rek - 6 * STAP);

      var oudeY = s.y;
      s.x += s.vx * STAP;
      s.y += s.vy * STAP;
      if (s.x < -16) s.x += BREEDTE + 32;
      if (s.x > BREEDTE + 16) s.x -= BREEDTE + 32;

      for (var i = 0; i < w.platforms.length; i++) {
        var p = w.platforms[i];
        if (p.gebroken) {
          p.val += 900 * STAP;
          p.y -= p.val * STAP;
        } else if (p.vx) {
          var rand = p.b / 2 + 6;
          p.x += p.vx * STAP;
          if ((p.x < rand && p.vx < 0) || (p.x > BREEDTE - rand && p.vx > 0)) p.vx = -p.vx;
        }
      }
      for (var j = 0; j < w.wespen.length; j++) {
        var wesp = w.wespen[j];
        wesp.fase += 1.6 * STAP;
        wesp.x = wesp.basis + Math.sin(wesp.fase) * 34;
      }

      if (!s.dood) {
        if (s.vy < 0) raakPlatform(s, oudeY);
        raakWesp(s);
        if (!s.dood) raakItem(s);
        w.punten = Math.max(w.punten, Math.floor((s.y - 30) / EENHEDEN_PER_PUNT));
      }

      if (s.y - w.cam > w.hoogte * 0.55) w.cam = s.y - w.hoogte * 0.55;
      genereer();
      w.platforms = w.platforms.filter(function (q) { return q.y > w.cam - 50; });
      w.wespen = w.wespen.filter(function (q) { return q.y > w.cam - 50; });
      w.items = w.items.filter(function (q) { return q.y > w.cam - 50; });
      if (s.y < w.cam - 70) w.afgelopen = true;
    };

    genereer();
    return w;
  }

  window.SpringspelWereld = maakWereld;
  window.SpringspelStap = STAP;

  var spel = document.getElementById("spel");
  if (!spel) return;

  var canvas = document.getElementById("speelveld");
  var ctx = canvas.getContext("2d");
  var scoreVak = document.getElementById("spel-score");
  var paneel = document.getElementById("spel-paneel");
  var paneelStart = document.getElementById("paneel-start");
  var paneelEinde = document.getElementById("paneel-einde");
  var speelKnop = document.getElementById("spel-speel");
  var verderKnop = document.getElementById("spel-verder");
  var eindscore = document.getElementById("spel-eindscore");
  var status = document.getElementById("spel-status");
  var opnieuwOpslaan = document.getElementById("spel-opnieuw-opslaan");
  var besteVak = document.getElementById("spel-beste");
  var scorebord = document.getElementById("scorebord");

  var vlaggen = JSON.parse(document.getElementById("spel-vlaggen").textContent);
  var logo = new Image();
  logo.src = spel.dataset.logo;
  logo.onload = function () { if (stand !== "speelt") teken(); };
  var ORANJE = "#E8792B";
  var HOOPKLEUREN = ["#E8792B", "#E0A23A", "#E07B5F"];
  var BLADKLEUREN = ["#E0A23A", "#E07B5F", "#95BF1D"];
  var GROEN = "#95BF1D", GROEN_DONKER = "#6E8F12", GROEN_LICHT = "#D6EC9B";
  var KLEUR = spel.dataset.kleur || GROEN;
  var rustig = window.matchMedia("(prefers-reduced-motion: reduce)");

  var hoogte = 640, schaal = 1, ratio = 1;
  var wereld = null;
  var stand = "menu";                  /* menu | speelt | pauze | einde */
  var ingedrukt = [];                  /* {id, richting}, laatste wint */
  var toetsen = { links: false, rechts: false };
  var vorige = 0, voorraad = 0;
  var stilstand = 0;                   /* het spel staat even stil na een steek */
  var klap = null;
  var waarschuwingY = 80;
  var deeltjes = [];
  var bladeren = [];
  for (var b = 0; b < 12; b++) {
    bladeren.push({ x: Math.random() * BREEDTE, y: Math.random(), r: 4 + Math.random() * 6, hoek: Math.random() * 6.28 });
  }

  /* ── Maat ── */
  function pasMaatAan() {
    var vlak = spel.getBoundingClientRect();
    if (!vlak.width) return;             /* nog niet zichtbaar: geen maat om mee te rekenen */
    ratio = Math.min(window.devicePixelRatio || 1, 2);
    schaal = vlak.width / BREEDTE;
    hoogte = vlak.height / schaal;
    /* Net onder de terugknop en de score, op elke telefoon even ver. */
    waarschuwingY = document.querySelector(".spel-boven").offsetHeight / schaal + 18;
    canvas.width = Math.round(vlak.width * ratio);
    canvas.height = Math.round(vlak.height * ratio);
    if (wereld) wereld.hoogte = hoogte;
    teken();
  }

  /* ── Tekenen ── */
  function pil(x, y, b, h, ronding) {
    var r = ronding || Math.min(b, h) / 2;
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + b, y, x + b, y + h, r);
    ctx.arcTo(x + b, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + b, y, r);
    ctx.closePath();
  }

  function schermY(y) { return hoogte - (y - wereld.cam); }

  function tekenBladeren() {
    ctx.fillStyle = "rgba(149,191,29,0.10)";
    bladeren.forEach(function (blad) {
      var v = hoogte + 40;
      var y = ((blad.y * v + wereld.cam * 0.25) % v) - 20;
      ctx.save();
      ctx.translate(blad.x, y);
      ctx.rotate(blad.hoek);
      ctx.beginPath();
      ctx.ellipse(0, 0, blad.r * 1.6, blad.r * 0.7, 0, 0, 6.29);
      ctx.fill();
      ctx.restore();
    });
  }

  /* Een laag gesnoeide haag: blok met ronde hoeken, stammetjes eronder en
     losse bladeren erop. De plek van elk blad volgt uit zijn nummer, zodat de
     haag niet flikkert; de bladeren zijn gelijk over de breedte verdeeld,
     want de heggen worden smaller naarmate je hoger komt. */
  function tekenHeg(p, y) {
    var links = p.x - p.b / 2;
    ctx.strokeStyle = "#6B5237";
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    ctx.beginPath();
    for (var st = links + 12; st < links + p.b - 6; st += 18) {
      ctx.moveTo(st, y + 14);
      ctx.lineTo(st, y + 20);
    }
    ctx.stroke();

    pil(links, y + 1, p.b, 16, 6);
    var verloop = ctx.createLinearGradient(0, y, 0, y + 17);
    verloop.addColorStop(0, "#7FA81A");
    verloop.addColorStop(1, "#4C6B12");
    ctx.fillStyle = verloop;
    ctx.fill();

    ctx.fillStyle = GROEN;
    var i = 0;
    for (var bx = links + 6; bx < links + p.b - 3; bx += 8, i++) {
      ctx.beginPath();
      ctx.arc(bx, y + 4, [4, 5, 3.8, 5.2][i % 4], 0, 6.29);
      ctx.fill();
    }
    var aantal = Math.round(p.b / 6);
    for (var j = 0; j < aantal; j++) {
      ctx.fillStyle = j % 3 ? "#A9D12E" : "#3E5A10";
      ctx.beginPath();
      ctx.ellipse(links + 5 + (j + 0.5) * (p.b - 10) / aantal, y + 8 + [0, 4, 2, 5, 1, 3][j % 6], 2.6, 1.4, j, 0, 6.29);
      ctx.fill();
    }
  }

  /* De tuin waar elk potje begint: schutting, tuinhuisje en de bus. Alleen
     decor; je springt van het gras eronder. */
  function tekenTuin() {
    var g = schermY(30);
    if (g - 130 > hoogte) return;

    ctx.fillStyle = "#4A3F2E";
    for (var x = 2; x < BREEDTE; x += 17) {
      pil(x, g - 46, 14, 50, 4);
      ctx.fill();
    }
    ctx.fillRect(0, g - 34, BREEDTE, 4);
    ctx.fillRect(0, g - 14, BREEDTE, 4);

    /* Tuinhuisje */
    pil(266, g - 58, 84, 62, 4);
    ctx.fillStyle = "#6B5237";
    ctx.fill();
    ctx.fillStyle = "#3B3F36";
    ctx.beginPath();
    ctx.moveTo(258, g - 56);
    ctx.lineTo(308, g - 84);
    ctx.lineTo(358, g - 56);
    ctx.closePath();
    ctx.fill();
    pil(278, g - 40, 22, 42, 3);
    ctx.fillStyle = "#4A3F2E";
    ctx.fill();
    pil(312, g - 42, 26, 20, 3);
    ctx.fillStyle = GROEN_LICHT;
    ctx.fill();

    /* De bestelbus van De Groene M, met de neus naar rechts. */
    ctx.beginPath();
    ctx.moveTo(14, g - 8);
    ctx.quadraticCurveTo(8, g - 8, 8, g - 14);
    ctx.lineTo(8, g - 68);
    ctx.quadraticCurveTo(8, g - 74, 14, g - 74);
    ctx.lineTo(106, g - 74);
    ctx.quadraticCurveTo(112, g - 74, 115, g - 69);
    ctx.lineTo(129, g - 44);
    ctx.quadraticCurveTo(146, g - 41, 147, g - 30);
    ctx.lineTo(148, g - 14);
    ctx.quadraticCurveTo(148, g - 8, 142, g - 8);
    ctx.closePath();
    ctx.fillStyle = "#EFEBDD";
    ctx.fill();
    ctx.save();
    ctx.clip();
    ctx.fillStyle = GROEN;
    ctx.fillRect(0, g - 26, BREEDTE, 7);
    ctx.restore();

    /* Raam in de cabine */
    ctx.beginPath();
    ctx.moveTo(101, g - 68);
    ctx.lineTo(110, g - 68);
    ctx.lineTo(123, g - 45);
    ctx.lineTo(101, g - 45);
    ctx.closePath();
    ctx.fillStyle = "#3B3F36";
    ctx.fill();

    /* Naden van de schuifdeur en het cabineportier */
    ctx.strokeStyle = "rgba(26,26,24,0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(95, g - 72);
    ctx.lineTo(95, g - 10);
    ctx.moveTo(127, g - 44);
    ctx.lineTo(127, g - 10);
    ctx.moveTo(62, g - 72);
    ctx.lineTo(62, g - 10);
    ctx.stroke();

    ctx.fillStyle = "#F2C230";
    pil(141, g - 34, 6, 7, 2);
    ctx.fill();
    ctx.fillStyle = "#3B3F36";
    pil(132, g - 14, 17, 5, 2);
    ctx.fill();
    pil(99, g - 49, 5, 6, 2);
    ctx.fill();

    if (logo.complete && logo.naturalWidth) ctx.drawImage(logo, 15, g - 66, 21, 18);
    ctx.fillStyle = "#1A1A18";
    ctx.font = "italic 600 8.5px Fraunces, serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText("De Groene M", 38, g - 57);

    [34, 123].forEach(function (wiel) {
      ctx.fillStyle = "#2A2C26";
      ctx.beginPath();
      ctx.arc(wiel, g - 7, 13.5, Math.PI, 0);
      ctx.fill();
      ctx.fillStyle = "#1A1A18";
      ctx.beginPath();
      ctx.arc(wiel, g - 6, 10.5, 0, 6.29);
      ctx.fill();
      ctx.fillStyle = "#8B8F83";
      ctx.beginPath();
      ctx.arc(wiel, g - 6, 4.5, 0, 6.29);
      ctx.fill();
    });
  }

  function tekenGras(y) {
    var verloop = ctx.createLinearGradient(0, y, 0, y + 30);
    verloop.addColorStop(0, GROEN);
    verloop.addColorStop(1, GROEN_DONKER);
    ctx.fillStyle = verloop;
    ctx.fillRect(0, y, BREEDTE, Math.max(30, hoogte - y + 40));
    ctx.fillStyle = "#A9D12E";
    for (var x = 3; x < BREEDTE; x += 7) {
      var lengte = 4 + (x * 7) % 5;
      ctx.beginPath();
      ctx.moveTo(x - 3, y + 1);
      ctx.lineTo(x, y - lengte);
      ctx.lineTo(x + 3, y + 1);
      ctx.closePath();
      ctx.fill();
    }
  }

  /* Kruiwagen van opzij, met het wiel in de rijrichting. */
  function tekenKruiwagen(p, y) {
    ctx.save();
    ctx.translate(p.x, y);
    if (p.vx < 0) ctx.scale(-1, 1);
    ctx.lineCap = "round";
    ctx.strokeStyle = "#8B7A5E";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(-30, 3);
    ctx.lineTo(-46, -1);
    ctx.stroke();
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-16, 10);
    ctx.lineTo(-19, 19);
    ctx.stroke();
    ctx.strokeStyle = "#5F6B6E";
    ctx.beginPath();
    ctx.moveTo(20, 9);
    ctx.lineTo(27, 15);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(27, 15, 7, 0, 6.29);
    ctx.fillStyle = "#2A2C26";
    ctx.fill();
    ctx.strokeStyle = "#8B8F83";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-32, 0);
    ctx.lineTo(36, 0);
    ctx.lineTo(30, 11);
    ctx.lineTo(-24, 11);
    ctx.closePath();
    ctx.fillStyle = "#8FA3A8";
    ctx.fill();
    pil(-33, -1, 70, 4, 2);
    ctx.fillStyle = "#B5C4C8";
    ctx.fill();
    ctx.restore();
  }

  /* Een lage hoop bladeren: twee rijen, plat genoeg om een platform te blijven. */
  function tekenBladerhoop(p, y) {
    var links = p.x - p.b / 2;
    pil(links, y + 5, p.b, 9, 4.5);
    ctx.fillStyle = "#A8602A";
    ctx.fill();
    [{ y: 11, n: 8, s: 0.9 }, { y: 5, n: 9, s: 1 }].forEach(function (rij, r) {
      var stap = (p.b - 12 * rij.s) / (rij.n - 1);
      for (var i = 0; i < rij.n; i++) {
        tekenBlad(links + i * stap, y + rij.y, [-0.17, 0.16, -0.09, 0.21, -0.21, 0.1][i % 6], HOOPKLEUREN[(i + r) % 3], rij.s);
      }
    });
  }

  function tekenHark(p, y) {
    var x = p.x + p.boost;
    ctx.strokeStyle = GROEN_LICHT;
    ctx.lineCap = "round";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x, y - 22);
    ctx.moveTo(x - 11, y - 22);
    ctx.lineTo(x + 11, y - 22);
    ctx.stroke();
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (var t = -11; t <= 11; t += 5.5) {
      ctx.moveTo(x + t, y - 22);
      ctx.lineTo(x + t, y - 29);
    }
    ctx.stroke();
  }

  function tekenPlatform(p) {
    var y = schermY(p.y);
    if (y < -50 || y > hoogte + 30) return;
    if (p.gebroken) return;                  /* de hoop is weggewaaid, zie verwerkEffecten */
    if (p.soort === "gras") tekenGras(y);
    else if (p.soort === "heg") tekenHeg(p, y);
    else if (p.soort === "kruiwagen") tekenKruiwagen(p, y);
    else tekenBladerhoop(p, y);
    if (p.boost !== undefined) tekenHark(p, y);
  }

  /* Waar collega's en je eigen record zitten: een stippellijn over de volle
     breedte met een vlaggetje, om en om links en rechts. */
  function tekenVlaggen() {
    ctx.font = "600 12px Inter, sans-serif";
    ctx.textBaseline = "middle";
    vlaggen.forEach(function (v, i) {
      var y = schermY(v.punten * EENHEDEN_PER_PUNT + 30);
      if (y < -30 || y > hoogte + 30) return;
      ctx.strokeStyle = v.ik ? "rgba(214,236,155,0.45)" : "rgba(255,255,255,0.18)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 7]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(BREEDTE, y);
      ctx.stroke();
      ctx.setLineDash([]);

      var links = i % 2 === 0;
      var x = links ? 14 : BREEDTE - 14;
      var kant = links ? 1 : -1;
      ctx.strokeStyle = "rgba(255,255,255,0.7)";
      ctx.lineCap = "round";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x, y - 26);
      ctx.stroke();
      ctx.fillStyle = v.kleur;
      ctx.beginPath();
      ctx.moveTo(x, y - 26);
      ctx.lineTo(x + kant * 17, y - 20);
      ctx.lineTo(x, y - 14);
      ctx.closePath();
      ctx.fill();
      ctx.textAlign = links ? "left" : "right";
      ctx.fillStyle = v.ik ? GROEN_LICHT : "rgba(255,255,255,0.8)";
      ctx.fillText(v.ik ? "Jouw record" : v.naam.slice(0, 14), x + kant * 4, y - 7);
    });
    ctx.textAlign = "left";
  }

  function tekenBlad(x, y, hoek, kleur, maat) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(hoek);
    if (maat) ctx.scale(maat, maat);
    ctx.fillStyle = kleur;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.bezierCurveTo(3, -4, 9, -4, 12, 0);
    ctx.bezierCurveTo(9, 4, 3, 4, 0, 0);
    ctx.fill();
    ctx.restore();
  }

  function tekenItem(item) {
    var y = schermY(item.y) + (rustig.matches ? 0 : Math.sin(wereld.tijd * 4 + item.x) * 3);
    ctx.save();
    ctx.translate(item.x, y);
    ctx.fillStyle = "rgba(214,236,155,0.20)";
    ctx.beginPath();
    ctx.arc(0, 0, 20, 0, 6.29);
    ctx.fill();
    if (item.soort === "imkerpak") {
      ctx.fillStyle = "#EFEBDD";
      ctx.beginPath();
      ctx.arc(0, -3, 8, Math.PI, 0);
      ctx.closePath();
      ctx.fill();
      pil(-13, -4, 26, 4);
      ctx.fill();
      ctx.fillStyle = "rgba(239,235,221,0.45)";
      pil(-10, 0, 20, 11, 4);
      ctx.fill();
    } else {
      /* Oranje handblazer met blaadjes uit de buis. */
      var wapper = rustig.matches ? 0 : Math.sin(wereld.tijd * 7) * 0.25;
      ctx.scale(0.85, 0.85);
      ctx.strokeStyle = "#3B3F36";
      ctx.lineWidth = 3.5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(-14, -9);
      ctx.bezierCurveTo(-13, -16, -3, -16, -2, -9);
      ctx.stroke();
      pil(-18, -10, 20, 14, 5);
      ctx.fillStyle = ORANJE;
      ctx.fill();
      ctx.fillStyle = "#EFEBDD";
      ctx.beginPath();
      ctx.moveTo(0, -5);
      ctx.lineTo(16, 3);
      ctx.lineTo(14, 8);
      ctx.lineTo(-2, 1);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#3B3F36";
      ctx.beginPath();
      ctx.arc(-9, -3, 3, 0, 6.29);
      ctx.fill();
      tekenBlad(15, -5, -0.4 + wapper, BLADKLEUREN[0]);
      tekenBlad(17, 6, 0.3 - wapper, BLADKLEUREN[1]);
      tekenBlad(8, 13, 0.9 + wapper, BLADKLEUREN[2]);
    }
    ctx.restore();
  }

  function tekenWesp(wesp) {
    var y = schermY(wesp.y);
    ctx.save();
    ctx.translate(wesp.x, y);
    ctx.fillStyle = "rgba(255,255,255,0.55)";
    var slag = rustig.matches ? 0 : Math.sin(wereld.tijd * 40) * 0.5;
    ctx.beginPath();
    ctx.ellipse(-4, -9, 5, 9, -0.5 + slag, 0, 6.29);
    ctx.ellipse(5, -9, 5, 9, 0.5 - slag, 0, 6.29);
    ctx.fill();
    pil(-13, -8, 26, 16);
    ctx.fillStyle = "#F2C230";
    ctx.fill();
    ctx.save();
    ctx.clip();
    ctx.fillStyle = "#1A1A18";
    ctx.fillRect(-6, -9, 4.5, 18);
    ctx.fillRect(2, -9, 4.5, 18);
    ctx.restore();
    ctx.restore();
  }

  function tekenHovenier(x, voet) {
    var s = wereld.speler;
    var rek = s.rek * s.rek;
    ctx.save();
    ctx.translate(x, schermY(voet));
    if (s.dood) {
      /* Uitgeteld: draait om zijn middel naar beneden. */
      ctx.translate(0, -22);
      ctx.rotate((wereld.tijd - s.doodOp) * 8);
      ctx.translate(0, 22);
    }
    ctx.scale(s.kijk * (1 + rek * 0.14), 1 - rek * 0.2);
    /* Knippert zolang niets je kan raken. */
    if (s.veilig > 0) ctx.globalAlpha = rustig.matches || Math.floor(wereld.tijd * 14) % 2 ? 0.55 : 1;
    var PAKKLEUR = "#EFEBDD";

    if (s.blazer > 0) {
      /* Bladblazer op de rug, met de lucht recht naar beneden. */
      ctx.strokeStyle = "rgba(255,255,255,0.6)";
      ctx.lineCap = "round";
      ctx.lineWidth = 2;
      ctx.beginPath();
      [-4, 0, 4].forEach(function (d) {
        ctx.moveTo(-17 + d, 6);
        ctx.lineTo(-17 + d * 1.6, 12 + (rustig.matches ? 6 : Math.random() * 12));
      });
      ctx.stroke();
      ctx.fillStyle = "#EFEBDD";
      pil(-20, -12, 6, 16, 3);
      ctx.fill();
      ctx.fillStyle = ORANJE;
      pil(-23, -34, 12, 25, 4);
      ctx.fill();
      ctx.fillStyle = "#3B3F36";
      ctx.beginPath();
      ctx.arc(-17, -25, 2.5, 0, 6.29);
      ctx.fill();
    }

    /* Laarzen */
    ctx.fillStyle = "#3B3F36";
    pil(-11, -7, 11, 7); ctx.fill();
    pil(1, -7, 11, 7); ctx.fill();
    /* Tuinbroek */
    pil(-11, -26, 22, 21, 6);
    ctx.fillStyle = s.pak ? PAKKLEUR : "#4C6B12";
    ctx.fill();
    /* Shirt in de eigen planbordkleur, met de bretels eroverheen */
    pil(-11, -34, 22, 14, 6);
    ctx.fillStyle = s.pak ? PAKKLEUR : KLEUR;
    ctx.fill();
    if (!s.pak) {
      ctx.fillStyle = "#4C6B12";
      ctx.fillRect(-7, -33, 3.5, 10);
      ctx.fillRect(3.5, -33, 3.5, 10);
    }
    /* Hoofd */
    ctx.fillStyle = "#F0C9A0";
    ctx.beginPath();
    ctx.arc(0, -41, 9, 0, 6.29);
    ctx.fill();
    ctx.fillStyle = "#1A1A18";
    ctx.beginPath();
    ctx.arc(4, -41, 1.5, 0, 6.29);
    ctx.fill();
    if (s.pak) {
      /* Imkerhoed met sluier */
      ctx.fillStyle = PAKKLEUR;
      ctx.beginPath();
      ctx.arc(0, -50, 8.5, Math.PI, 0);
      ctx.closePath();
      ctx.fill();
      pil(-15, -51, 30, 4);
      ctx.fill();
      ctx.fillStyle = "rgba(239,235,221,0.42)";
      pil(-12, -48, 24, 18, 6);
      ctx.fill();
    } else {
      /* Pet met klep */
      ctx.fillStyle = GROEN;
      ctx.beginPath();
      ctx.arc(0, -44, 9.5, Math.PI, 0);
      ctx.closePath();
      ctx.fill();
      pil(3, -46, 12, 3.5);
      ctx.fill();
    }
    ctx.restore();
  }

  function tekenPijlen() {
    var over = 2.5 - wereld.tijd;
    if (over <= 0 || (besturing === "kantelen" && kanteling !== null)) return;
    ctx.strokeStyle = "rgba(255,255,255," + Math.min(0.5, over * 0.5) + ")";
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    [[34, -1], [BREEDTE - 34, 1]].forEach(function (pijl) {
      ctx.beginPath();
      ctx.moveTo(pijl[0] - pijl[1] * 8, hoogte - 90);
      ctx.lineTo(pijl[0] + pijl[1] * 8, hoogte - 72);
      ctx.lineTo(pijl[0] - pijl[1] * 8, hoogte - 54);
      ctx.stroke();
    });
  }

  function ster(x, y, r) {
    ctx.beginPath();
    for (var i = 0; i < 10; i++) {
      var straal = i % 2 ? r * 0.45 : r;
      var hoek = -Math.PI / 2 + i * Math.PI / 5;
      ctx.lineTo(x + Math.cos(hoek) * straal, y + Math.sin(hoek) * straal);
    }
    ctx.closePath();
    ctx.fill();
  }

  /* Een geel uitroepteken bovenin, recht boven de plek waar de wesp straks
     in beeld komt. Hij schuift mee met de wesp en verdwijnt zodra die er is. */
  function tekenWaarschuwing(wesp) {
    var y = schermY(wesp.y);
    if (y >= waarschuwingY) return;
    var x = Math.max(20, Math.min(BREEDTE - 20, wesp.x));
    var puls = rustig.matches ? 1 : 1 + Math.sin(wereld.tijd * 9) * 0.08;
    ctx.save();
    ctx.translate(x, waarschuwingY);
    ctx.scale(puls, puls);
    ctx.fillStyle = "#F2C230";
    ctx.beginPath();
    ctx.arc(0, 0, 15, 0, 6.29);
    ctx.fill();
    ctx.fillStyle = "#1A1A18";
    pil(-2.5, -9, 5, 12);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, 7, 2.8, 0, 6.29);
    ctx.fill();
    ctx.restore();
  }

  function tekenKlap(dt) {
    if (!klap) return;
    klap.leven -= dt;
    if (klap.leven <= 0) { klap = null; return; }
    var y = schermY(klap.y);
    var verloop = 1 - klap.leven / 0.4;
    ctx.globalAlpha = Math.min(1, klap.leven * 5);
    ctx.fillStyle = "#FFFFFF";
    ster(klap.x, y, 22 + verloop * 26);
    ctx.fillStyle = "#F2C230";
    ster(klap.x, y, 13 + verloop * 16);
    ctx.globalAlpha = 1;
  }

  function tekenSterretjes(s) {
    var hoofd = schermY(s.y) - 62;
    ctx.fillStyle = "#F2C230";
    for (var i = 0; i < 3; i++) {
      var hoek = (wereld.tijd - s.doodOp) * 7 + i * 2.09;
      ster(s.x + Math.cos(hoek) * 20, hoofd + Math.sin(hoek) * 6, 5.5);
    }
  }

  function verwerkEffecten() {
    wereld.effecten.forEach(function (e) {
      if (e.soort === "steek") {
        klap = { x: e.x, y: e.y, leven: 0.4 };
        stilstand = 0.22;
      }
      if (rustig.matches) return;
      if (e.soort === "breek") {
        for (var b = 0; b < 16; b++) {
          deeltjes.push({
            x: e.x + (Math.random() - 0.5) * 60,
            y: e.y + 4,
            vx: (Math.random() - 0.5) * 200,
            vy: 60 + Math.random() * 220,
            leven: 0.75,
            kleur: HOOPKLEUREN[b % 3],
            hoek: Math.random() * 6.28,
          });
        }
        return;
      }
      var aantal = e.soort === "land" ? 4 : 10;
      for (var i = 0; i < aantal; i++) {
        deeltjes.push({
          x: e.x, y: e.y,
          vx: (Math.random() - 0.5) * 220,
          vy: Math.random() * 200,
          leven: 0.45,
          kleur: e.soort === "land" || e.soort === "boost" ? GROEN : "#F2C230",
        });
      }
    });
    wereld.effecten.length = 0;
  }

  /* Tijdens het blazen waaien er blaadjes onder de hovenier uit. */
  function blaasBlaadjes(s, dt) {
    if (s.blazer <= 0 || rustig.matches || Math.random() > dt * 28) return;
    deeltjes.push({
      x: s.x - s.kijk * 17,
      y: s.y - 12,
      vx: (Math.random() - 0.5) * 240,
      vy: 200 + Math.random() * 200,
      leven: 0.8,
      kleur: BLADKLEUREN[Math.floor(Math.random() * BLADKLEUREN.length)],
      hoek: Math.random() * 6.28,
    });
  }

  function tekenDeeltjes(dt) {
    deeltjes = deeltjes.filter(function (d) {
      d.leven -= dt;
      d.vy -= 700 * dt;
      d.x += d.vx * dt;
      d.y += d.vy * dt;
      if (d.leven <= 0) return false;
      ctx.globalAlpha = Math.min(1, d.leven * 3);
      if (d.hoek !== undefined) {
        d.hoek += 6 * dt;
        tekenBlad(d.x, schermY(d.y), d.hoek, d.kleur);
        return true;
      }
      ctx.fillStyle = d.kleur;
      ctx.beginPath();
      ctx.arc(d.x, schermY(d.y), 2.5, 0, 6.29);
      ctx.fill();
      return true;
    });
    ctx.globalAlpha = 1;
  }

  function teken(dt) {
    ctx.setTransform(ratio * schaal, 0, 0, ratio * schaal, 0, 0);
    ctx.clearRect(0, 0, BREEDTE, hoogte);
    if (!wereld) return;
    if (klap && !rustig.matches) ctx.translate(Math.sin(klap.leven * 90) * 5 * klap.leven, 0);
    tekenBladeren();
    tekenVlaggen();
    tekenTuin();
    wereld.platforms.forEach(tekenPlatform);
    wereld.items.forEach(tekenItem);
    wereld.wespen.forEach(tekenWesp);
    var s = wereld.speler;
    tekenHovenier(s.x, s.y);
    /* Half over de rand: ook aan de andere kant tekenen. */
    if (s.x < 16) tekenHovenier(s.x + BREEDTE + 32, s.y);
    if (s.x > BREEDTE - 16) tekenHovenier(s.x - BREEDTE - 32, s.y);
    verwerkEffecten();
    blaasBlaadjes(s, dt || 0);
    tekenDeeltjes(dt || 0);
    if (s.dood) tekenSterretjes(s);
    else if (stand === "speelt") wereld.wespen.forEach(tekenWaarschuwing);
    tekenKlap(dt || 0);
    if (stand === "speelt") tekenPijlen();
  }

  /* ── Lus ── */
  function richting() {
    if (besturing === "kantelen" && kanteling !== null) return Math.abs(kanteling) < 0.08 ? 0 : kanteling;
    if (ingedrukt.length) return ingedrukt[ingedrukt.length - 1].richting;
    return (toetsen.rechts ? 1 : 0) - (toetsen.links ? 1 : 0);
  }

  function lus(nu) {
    if (stand !== "speelt") return;
    var dt = Math.min(0.1, (nu - vorige) / 1000);
    vorige = nu;
    if (stilstand > 0) {
      stilstand -= dt;
    } else {
      voorraad += dt;
    }
    var r = richting();
    while (voorraad >= STAP && !wereld.afgelopen) {
      wereld.stap(r);
      voorraad -= STAP;
    }
    if (String(wereld.punten) !== scoreVak.textContent) scoreVak.textContent = wereld.punten;
    teken(dt);
    if (wereld.afgelopen) einde();
    else requestAnimationFrame(lus);
  }

  function hervat() {
    stand = "speelt";
    verderKnop.hidden = true;
    vorige = performance.now();
    voorraad = 0;
    requestAnimationFrame(lus);
  }

  /* ── Server ── */
  /* Op volgorde: een score moet aankomen na zijn eigen start en vóór de
     start van het volgende potje, ook als iemand snel op Nog een keer tikt. */
  var wachtrij = Promise.resolve();

  function verstuurPost(url, inhoud) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": spel.dataset.csrf },
      body: inhoud,
    });
  }

  function meldStart() {
    wachtrij = wachtrij.then(function () {
      return verstuurPost(spel.dataset.startUrl, "{}");
    }).catch(function () {});
  }

  function slaOp(punten) {
    status.textContent = "";
    opnieuwOpslaan.hidden = true;
    wachtrij = wachtrij.then(function () {
      return verstuurPost(spel.dataset.scoreUrl, JSON.stringify({ punten: punten }));
    }).then(function (antwoord) {
      if (antwoord.status === 400) {
        status.textContent = "Deze score kon niet worden opgeslagen.";
        return;
      }
      if (!antwoord.ok) throw new Error("server");
      return antwoord.json().then(function (data) {
        scorebord.innerHTML = data.scorebord;
        spel.dataset.beste = data.beste;
        vlaggen = data.vlaggen;
        besteVak.textContent = data.beste;
        status.textContent = data.nieuw_record ? "Nieuw record!" : "Jouw beste: " + data.beste;
      });
    }).catch(function () {
      status.textContent = "Score niet opgeslagen, geen verbinding.";
      opnieuwOpslaan.hidden = false;
      opnieuwOpslaan.onclick = function () { slaOp(punten); };
    });
  }

  /* ── Standen ── */
  function begin() {
    wereld = maakWereld(hoogte, Math.random);
    deeltjes = [];
    klap = null;
    stilstand = 0;
    ingedrukt = [];
    paneel.hidden = true;
    scoreVak.hidden = false;
    scoreVak.textContent = "0";
    meldStart();
    hervat();
  }

  function einde() {
    stand = "einde";
    ingedrukt = [];
    scoreVak.hidden = true;
    paneelStart.hidden = true;
    paneelEinde.hidden = false;
    eindscore.textContent = wereld.punten;
    speelKnop.textContent = "Nog een keer";
    paneel.hidden = false;
    paneel.scrollTop = 0;
    slaOp(wereld.punten);
  }

  function pauzeer() {
    if (stand !== "speelt") return;
    stand = "pauze";
    ingedrukt = [];
    verderKnop.hidden = false;
  }

  /* ── Besturing ── */
  spel.addEventListener("pointerdown", function (e) {
    if (stand !== "speelt" || e.target.closest("a, button")) return;
    var vlak = spel.getBoundingClientRect();
    ingedrukt.push({ id: e.pointerId, richting: e.clientX - vlak.left < vlak.width / 2 ? -1 : 1 });
  });
  function laatLos(e) {
    ingedrukt = ingedrukt.filter(function (v) { return v.id !== e.pointerId; });
  }
  window.addEventListener("pointerup", laatLos);
  window.addEventListener("pointercancel", laatLos);
  spel.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  /* Tijdens het spelen mag de pagina nergens heen, ook niet met de
     rubberband van iOS; in het paneel moet je wel kunnen scrollen. */
  document.addEventListener("touchmove", function (e) {
    if (stand === "speelt") e.preventDefault();
  }, { passive: false });

  function zetToets(e, aan) {
    if (e.key === "ArrowLeft" || e.key === "a") toetsen.links = aan;
    else if (e.key === "ArrowRight" || e.key === "d") toetsen.rechts = aan;
    else return;
    e.preventDefault();
  }
  window.addEventListener("keydown", function (e) { zetToets(e, true); });
  window.addEventListener("keyup", function (e) { zetToets(e, false); });

  /* Kantelen is een keuze op het startscherm, alleen op een toestel dat het
     kan. Zonder sensorgegevens blijft tikken gewoon werken. */
  var VOLLE_KANTELING = 25;            /* zoveel graden is volle snelheid */
  var besturing = "tikken";
  var kanteling = null;
  var keuzeBalk = document.getElementById("spel-besturing");

  function leesKanteling(e) {
    if (e.gamma === null) return;
    var scherm = (window.screen.orientation && window.screen.orientation.angle) || 0;
    var hoek = scherm === 90 ? e.beta : scherm === 270 ? -e.beta : scherm === 180 ? -e.gamma : e.gamma;
    var doel = Math.max(-1, Math.min(1, hoek / VOLLE_KANTELING));
    kanteling = kanteling === null ? doel : kanteling + (doel - kanteling) * 0.35;
  }

  function kiesBesturing(soort) {
    besturing = soort;
    keuzeBalk.querySelectorAll("[data-besturing]").forEach(function (knop) {
      knop.setAttribute("aria-pressed", knop.dataset.besturing === soort ? "true" : "false");
    });
    try { localStorage.setItem("spel-besturing", soort); } catch (e) {}
  }

  /* iOS vraagt toestemming, en dat moet vanuit een tik gebeuren. */
  function vraagSensor() {
    if (!window.DeviceOrientationEvent.requestPermission) return Promise.resolve(true);
    return window.DeviceOrientationEvent.requestPermission().then(function (antwoord) {
      return antwoord === "granted";
    }, function () { return false; });
  }

  if ("DeviceOrientationEvent" in window && window.matchMedia("(pointer: coarse)").matches) {
    keuzeBalk.hidden = false;
    window.addEventListener("deviceorientation", leesKanteling);
    keuzeBalk.addEventListener("click", function (e) {
      var knop = e.target.closest("[data-besturing]");
      if (knop) kiesBesturing(knop.dataset.besturing);
    });
    try {
      if (localStorage.getItem("spel-besturing") === "kantelen") kiesBesturing("kantelen");
    } catch (e) {}
  }

  speelKnop.addEventListener("click", function () {
    if (besturing !== "kantelen") return begin();
    vraagSensor().then(function (mag) {
      if (!mag) kiesBesturing("tikken");
      begin();
    });
  });
  verderKnop.addEventListener("click", hervat);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) pauzeer();
  });
  window.addEventListener("resize", pasMaatAan);

  wereld = maakWereld(hoogte, Math.random);
  pasMaatAan();
})();
