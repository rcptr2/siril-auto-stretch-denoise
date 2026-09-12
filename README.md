# Siril Auto Stretch & Denoise

Automatikus csillagköd képfeldolgozó Python script Siril-hez.

## Funkciók

### 🎯 Automatikus Nyújtás (Stretch)
- **Intelligens fekete/fehér pont detektálás** a kijelölt háttérterület alapján
- **MTF görbék alkalmazása** (Curves3 stílus)
- **Gamma korrekció** természetes megjelenéshez
- **Többlépcsős feldolgozás** a finom kontrollhoz
- **Csúcsfények megőrzése** (nem égnek ki)

### 🎭 Zajmintán Alapuló Maszkolás
- A kijelölt háttérterület vizsgálata zajmintának
- Hasonló fényerejű/színű területek automatikus azonosítása
- Szelektív szűrés csak a zajterületeken
- Csillagköd részek megóvása

### 🧹 Adaptív Zajszűrés
- **Non-Local Means (NLM) szűrés** RGB képekhez
- **Medián szűrés** monokróm képekhez
- Erősség kontroll a zajmaszk alapján
- Természetes megjelenés megőrzése

### 🎨 Kontrasztkiigazítás
- **Szelektív kontrasztnövelés** csak a zajterületeken
- LAB színtérre alapuló feldolgozás a természetesebb szín megőrzéshez
- Enyhe kiigazítás az égi ég sötét aspektusához

### 🔒 Háttér Szint Stabilizálás
- Cél háttér szint: **0.18** (konfigurálható)
- Automatikus szint korrekció a feldolgozás alatt
- Sötét égbolt megjelenés megőrzése

## Telepítés

### Előfeltételek
- Python 3.7+
- pip

### Függőségek Automatikus Telepítése

A script automatikusan ellenőrzi és telepíti a szükséges csomagokat az első futtatásakor:

```bash
python siril_auto_stretch.py /path/to/image.tif
```

### Manuális Telepítés (opcionális)

```bash
pip install -r requirements.txt
```

## Használat

### Lépésről Lépésre

#### 1. Kép Megnyitása Siril-ben
```bash
# Siril megnyitása
Siril

# Kép betöltése: File > Open
```

#### 2. Háttér Kijelölése
- **Select > Selection Tools** vagy magическая varázsdálca
- Jelöld ki a **CSAK háttérből** álló terület(ek)et
- ⚠️ **Fontos**: Kerüld el a csillagok és csillagköd részeket!
- Több kijelölés is lehetséges (Shift + klikk)

#### 3. Kijelölés Mentése
```
Select > Save Selection as FITS
```
Mentsd el pl. `background_selection.fits`

#### 4. Script Futtatása

```bash
# Alapértelmezett mód (egyszerű megadás)
python siril_auto_stretch.py
# A script kéri meg a kép elérési útját

# Vagy direkt megadás
python siril_auto_stretch.py /path/to/your/image.tif
```

#### 5. Interaktív Lépések

A script futása alatt:
1. Kéri a feldolgozandó kép elérési útját
2. Irányítások a háttér kijelöléshez Siril-ben
3. Kéri a mentett kijelölés FITS fájljának elérési útját
4. **Automatikus feldolgozás** (nincs szükség további beavatkozásra)

```
🔬 Siril Auto Stretch & Denoise
✅ Kép betöltve: image.tif
   Méret: (3840, 2560, 3)
   Tartomány: 0.0032 - 0.9847

🎯 Háttér kijelölés:
   1. Nyisd meg a képet Siril-ben
   2. Jelöld ki a CSAK háttérből álló terület(ek)et
   3. A kijelölést mentsd: Siril > Select > Save Selection as FITS
   4. Add meg a mentett kijelölés fájl elérési útját

📁 Kijelölés FITS fájl elérési útja: background_selection.fits
✅ Kijelölés betöltve: 425000 pixel

✅ Háttérminta: 425000 pixel
   Átlag: 0.1234
   Szórás: 0.0156

📊 Nyújtás paraméterek:
   Fekete pont: 0.0900
   Középpont (gamma): 0.7000
   Fehér pont: 0.9200

✅ Nyújtás alkalmazva
   Új tartomány: 0.0000 - 1.0000

🔍 Háttér szint ellenőrzés:
   Cél: 0.1800
   Aktuális: 0.1823
   ✅ Háttér szint megfelelő

🎭 Zajmaszk létrehozása...
✅ Zajmaszk készült: 320000 pixel (erős)

🧹 Adaptív zajszűrés alkalmazása (erőssége: 70.0%)...
✅ Zajszűrés kész

🎨 Szelektív kontrasztkiigazítás (erőssége: 15.0%)...
✅ Kontrasztkiigazítás kész

💾 Kép mentve: image_processed.tif

============================================================
✅ FELDOLGOZÁS KÉSZ!
============================================================
```

#### 6. Eredmény Megtekintése

A feldolgozott kép alapértelmezetten `<eredeti_nev>_processed.tif` néven mentődik ugyanabban a könyvtárban.

```bash
# Megnyitás Siril-ben az ellenőrzéshez
Siril image_processed.tif
```

## Paraméterek Testreszabása

Ha szerkeszteni szeretnél részleteket, nyisd meg a `siril_auto_stretch.py` fájlt és módosítsd ezeket az értékeket:

```python
# Háttér szint ellenőrzés
self.verify_background_level(target_level=0.18)  # Sötétség szintje

# Zajmaszk létrehozása
noise_mask = self.create_noise_mask(
    dilation=3,   # Dilate kernel mérete
    blur=15       # Gaussian blur kernel mérete
)

# Zajszűrés erőssége
self.apply_adaptive_denoising(noise_mask, strength=0.7)  # 0-1

# Kontrasztkiigazítás erőssége
self.enhance_contrast_selective(noise_mask, strength=0.15)  # 0-1
```

## Támogatott Formátumok

- **Input**: TIFF, PNG, FITS, JPG, BMP és más általános formátumok
- **Output**: TIFF (16-bit ajánlott astrofotográfiához)

## Hibaelhárítás

### "A kép nem tölthető be"
- Ellenőrizd az elérési útvonalat
- Bizonyosodj meg, hogy a fájl nem sérült

### "Kijelölés nem tölthető be"
- Ellenőrizd a FITS fájl elérési útját
- Ha PPM-ből mentettél, próbáld meg a FITS formátumot

### "Háttér szint nem megfelelő"
- A kijelölésnek nagyobb területet kell fednie
- Ügyelj arra, hogy ne legyenek csillagok a kijelölésben

## Fejlesztés

### Jövőbeli Fejlesztések
- Grafikus felület (GUI) Siril integrációval
- Batch feldolgozás több képhez
- Konfigurációs fájl támogatás
- Előnézetablak a paraméter módosítás során

## Licenc

MIT License - Szabadon használható és módosítható

## Szerző

rcptr2 - 2026

## Megjegyzések Asztrofotósoknak

💡 **Tippek a legjobb eredményekhez:**

1. **Háttér kijelölés**: Válassz olyan területet, ahol nincs csillag vagy köd
2. **Kijelölés mérete**: Minél nagyobb, annál jobb statisztika
3. **Többszöri futtatás**: Ha nem vagy elégedett, módosítsd az erősség paramétereket
4. **Összehasonlítás**: Nyitott meg az eredeti és feldolgozott képet egymás mellett
5. **Siril integrációs lépések**: Ezt követően további post-processing alkalmazható Siril-ben

---

**Megjegyzés**: Ez a script az asztrofotográfia feldolgozási munkafolyamatát hivatott gyorsítani. Az eredmény mindig függ az eredeti kép minőségétől és a háttér kijelölés pontosságától.
