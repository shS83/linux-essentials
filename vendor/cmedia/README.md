# Cmedia — differentiaalinen piirtokorjaus v2

Korjauspaketti projektille https://github.com/shS83/cmedia (root-haara).

**Tämä paketti päivittää cmedian omasta lähdekoodista.** Mukana on
asennusskripti ja turvallinen korjaustyökalu, ei koko alkuperäisen
projektin lähdekoodia. Voit osoittaa asenninta omaan klooniisi. Ilman
parametria asennin kloonaa lähdekoodin GitHubista väliaikaiseen kansioon.

## Mikä muuttui?

Edellisessä V1-versiossa `draw_browser()` päivitti jo muuttuneet
listan rivit, mutta tyhjensi oikean esikatselupaneelin kokonaan aina
valinnan vaihtuessa. Piirtorutiini myös kutsui kirjoitusta ja flushia
monesti yhden näppäinpainalluksen aikana, mikä saattoi aiheuttaa
havaittavaa välähtelyä.

V2:

* pitää tiedostolistan rivit, otsikon, tilarivin ja esikatselun erillisinä
  piirtovälimuisteina
* ei lähetä `ESC[2J`-koko ruudun tyhjennystä nuolinäppäimistä,
  PageUp/PageDown-, Home/End- eikä tavallisesta vierityksestä
* kirjoittaa **vain muuttuneet listan rivit** eikä koskaan pyyhi
  listapalkkeja esikatselua vaihdettaessa
* pitää esikatselun kehykset paikallaan, ja päivittää metatiedoista vain
  muuttuneet rivit
* päivittää kuvanvaihdossa vain kuvan sisäalueen; vanhat kuvat täytyy
  poistaa esikatselusta ennen seuraavan piirtoa
* lähettää kaikki yhden päivityksen tekstin ja grafiikan yhdessä
  stdout-kirjoituksessa (ei vaiheittaisia flush-kutsuja)
* tekee koko ruudun alustuksen vain uudessa hakemistossa, koon muuttuessa,
  ulkoasun muuttuessa tai palattaessa koko ruudun mediatilasta
* ei muuta Chafan, Kittyn, Sixelin, Pygamen eikä FFmpegin koodia

## Asennus

### Käytä olemassa olevaa cmedia-kloonia

```bash
unzip cmedia-differential-v2.zip
cd cmedia-differential-v2
./install.sh "$HOME/Code/cmedia"
```

Ohjelma varmuuskopioi tarvittaessa lähdetiedoston nimellä
`src/cmedia/app.py.before-diff-v2.bak`, muuttaa `draw_browser()`-funktion
ja asentaa käynnistimen `~/.local/bin/cmedia` käyttäjän omaan `uv tool`
-ympäristöön. Olemassa olevia asetuksia ei poisteta.

### Asenna GitHubista ilman paikallista kloonia

```bash
./install.sh
```

Tämä edellyttää toimivaa internetyhteyttä, `git`, `uv` ja `python3`-komentoja.
Cmedian alkuperäisen ohjelman edellyttämät `chafa`, `ffmpeg` ja Python
3.13+ tarvitaan edelleen. `uv` voi tarvittaessa hakea Pythonin.

Testaa:

```bash
command -v cmedia
cmedia ~/Pictures
```

## Jos haluat tehdä muutokset lähdekoodiin asentamatta

```bash
python3 patch_cmedia.py "$HOME/Code/cmedia"
git -C "$HOME/Code/cmedia" diff -- src/cmedia/app.py
```

Korjaustyökalu ei yritä tuntemattoman lähdekoodin muokkausta. V2:n
uudelleenajaminen on turvallista: se tunnistaa jo asennetun korjauksen.

## Testit

```bash
python3 tests/test_patch.py
bash tests/test_installer.sh
```

Testit tarkistavat mm. nuolien välkkymättömyyden ANSI-komentotasolla,
vierityksen, uudelleenpiirron koon muuttuessa ja asennuksen mock-uv:lla.
Kittyn ja Sixelin graafista käyttäytymistä pitää vielä testata
käytännössä käyttäjän päätelaitteella.
