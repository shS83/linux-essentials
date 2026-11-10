# cmedia — differentiaalinen selainpiirto + käyttäjäasennus

Tämä **ei ole koko cmedia-lähdekoodi**, vaan shS83/cmedia-projektin `root`-haaraan kohdistettu automaattinen korjaus- ja asennuspaketti. Asennin käyttää omaa Git-kloonia tai lataa alkuperäisen julkisen lähdekoodin. Git ja uv tarvitaan asennusvaiheessa.

## Asenna

Pura ZIP ja suorita sen kansiossa:

```bash
chmod +x install.sh
./install.sh ~/Code/cmedia
```

Jos projektisi on eri hakemistossa, korvaa polku oikealla. Halutessasi voit ajaa `./install.sh` ilman parametria; asennin hakee projektin GitHubista, jos paikallista projektia ei ole nykyhakemistossa.

Asennuksen jälkeen **`~/.local/bin/cmedia`** toimii käynnistimenä kaikista hakemistoista, kun `~/.local/bin` on PATHissa.

```bash
cmedia ~/Pictures
```

## Muutokset

- Nuolinäppäimet päivittävät vain muuttuvat tiedostolistan rivit: taustapalkkeja ei tyhjennetä koko terminaalin pyyhkimisellä.
- Valitun rivin vanha ja uusi tyyli kirjoitetaan koko listaleveydelle, ettei vanhoja korostuksia jää näkyviin.
- Esikatselu ja metatiedot päivittyvät valinnan vaihtuessa. Koko näytön uudelleenpiirto tehdään vain näkymän vaihtumisessa tai terminaalin koon muuttuessa.
- Nykyiset kuvanäyttöön, Chafaan, Kittyyn, Sixeliin ja Pygameen liittyvät toiminnot säilyvät alkuperäisestä lähdekoodista.
- Muuttuneesta `app.py`-tiedostosta tehdään `app.py.bak`-varmuuskopio, eikä korjausta yritetä asentaa kahdesti.

Huom. Paketin sisältämää korjausta on tarkastettu syntaksin ja paikallisten testien avulla. Lopullista toimintaa Kitty/Sixel-päätteessä ei ole testattu tässä ympäristössä.

## Git

Kun käytät omaa projektikansiotasi, tarkista muutokset:

```bash
cd ~/Code/cmedia
git diff
git add src/cmedia/app.py
git commit -m 'Render browser rows incrementally and add user installer'
git push
```

Varmuuskopiotiedosto `app.py.bak` ei kuulu commitiin.
