# Tooling Control Tower

Streamlit aplikacija za pregled kvarova, preventive, udaraca, rezervnih delova,
dokumentacije i akcionog plana alatnice.

## Fajlovi potrebni za objavljivanje

- `app.py` — glavni fajl aplikacije
- `requirements.txt` — Python paketi koje Streamlit Cloud instalira
- `background_tooling.png` i `company_logo.png` — slike interfejsa
- `smene.json` — početni podaci o broju smena
- `config.json` — već podešena veza za upis u Google Sheets
- `.streamlit/config.toml` — podešavanje Streamlit aplikacije
- `.gitignore` — izuzima nepotrebne lokalne fajlove

## 1. Postavljanje na GitHub

1. Prijavi se na [github.com](https://github.com/).
2. Klikni **New repository**.
3. Kao naziv možeš uneti `tooling-control-tower`.
4. Izaberi **Public** da bi repozitorijum i aplikacija mogli biti javno dostupni.
5. Nemoj uključivati GitHub opcije za automatsko pravljenje README ili `.gitignore`
   fajla, pošto su oni već pripremljeni.
6. Klikni **Create repository**.
7. Na sledećoj stranici izaberi **uploading an existing file**.
8. Raspakuj ZIP paket na računaru, otvori folder
   `Tooling_Control_Tower_GitHub` i prevuci **sav sadržaj foldera** na GitHub.
   Važno: `app.py` mora da bude u glavnom nivou repozitorijuma.
9. U polje za opis izmene unesi `Prva verzija aplikacije` i klikni
   **Commit changes**.

## 2. Objavljivanje na Streamlit Community Cloud

1. Otvori [share.streamlit.io](https://share.streamlit.io/) i prijavi se GitHub
   nalogom.
2. Klikni **Create app**.
3. Izaberi svoj repozitorijum i granu `main`.
4. Kao **Main file path** unesi `app.py`.
5. Otvori **Advanced settings**.
6. Izaberi Python **3.12**.
7. Polje **Secrets** ostavi prazno.
8. Sačuvaj podešavanja i klikni **Deploy**.
9. U podešavanjima deljenja aplikaciju postavi kao javnu. Svako ko dobije njen
   Streamlit link moći će da je otvori.

## Lokalno pokretanje

U folderu aplikacije pokreni:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Možeš koristiti i `Pokreni_Tooling_Control_Tower.bat` nakon instaliranja paketa.
Veza za Google Sheets je već podešena u `config.json`.

## Važne napomene

- Google Sheets izvori moraju biti dostupni aplikaciji preko linkova koje koristi
  `app.py`. Ako listovi nisu javni ili pravilno deljeni, učitavanje podataka neće
  raditi na Streamlit Cloud-u.
- Izmene fajla `smene.json` napravljene unutar Streamlit Cloud aplikacije nisu
  trajna baza podataka. Mogu nestati posle ponovnog pokretanja ili nove verzije
  aplikacije. Za trajno čuvanje novih smena potreban je Google Sheets, baza
  podataka ili drugi udaljeni servis.
- Aplikacija je pripremljena za javno korišćenje i ne zahteva Streamlit Secrets.
