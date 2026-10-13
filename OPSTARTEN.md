# Opstarten met een nieuw Claude-account

**Zelfde computer?** Dan hoef je niets te regelen. De repo staat in
`C:\Users\flori\development` en GitHub-toegang zit in Windows, niet in je
Claude-account. Open die map in Claude Code; de `CLAUDE.md`-bestanden worden
vanzelf gelezen.

**Andere computer, of een lege start?** Plak dan het blok hieronder als eerste
bericht in Claude Code. Claude zoekt zelf uit wat er al staat en helpt je met
de rest.

---

```
Ik ben Floris (HandigerAI). Ik werk aan de repo
https://github.com/kennismaken-wq/development (publiek): in de root een
Flask-huisstijltool, in klusapp/ de Django-app voor De Groene M. Help me stap
voor stap aan de slag, en leg alleen uit wat ik echt moet doen:

1. Kijk of git op deze computer staat. Zo niet: vertel hoe ik het installeer.
2. Kijk of er al een kloon van de repo is (eerst in C:\Users\flori\development,
   anders vraag je waar). Zo niet: clone hem. Zo wel: git pull.
3. Kijk of ik kan pushen (git push --dry-run). Lukt dat niet, help me dan
   inloggen bij GitHub via de browser (Git Credential Manager of gh auth
   login). Nooit een token in een bestand of in de repo.
4. Lees CLAUDE.md in de root, klusapp/CLAUDE.md, klusapp/CONTEXT.md en
   klusapp/docs/SPEC.md, en vat in een paar regels samen waar het project staat.
5. Zet de klusapp lokaal op zoals klusapp/CLAUDE.md beschrijft (venv,
   requirements, migrate, maak_testdata.py) en draai de tests.

Houd je daarna aan de afspraken in de CLAUDE.md-bestanden.
```
