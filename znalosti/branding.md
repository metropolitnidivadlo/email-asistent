# Vizuální identita – Metropolitní divadlo Praha

Zdroj: CSS Elementoru na https://metropolitnidivadlo.cz/wp-content/uploads/elementor/css/ (post-10.css = globální barvy webu, post-7/507/642/1256.css = stránky) a logo SVG. Web běží na WordPressu + Elementor.

## Barvy z webu (skutečné hodnoty)
- Hlavní červená (akcent): #F64A41 (--e-global-color-23e8c2d; ikony, tlačítka)
- Tmavší červená: #D5291F (--e-global-color-56676da)
- Červená v logu: #E13233
- Černá / téměř černá: #171717 (tlačítka), #060606 (nadpisy), #0D0D0D, #1E1E1E, #000000 (logo kruh, overlay)
- Šedá: #444444 (hover tlačítek, okraje)
- Bílá: #FFFFFF (pozadí sloupců, text na tmavém)
- Pozadí slidu hlavní stránky: #833ca3 (fialová, jednorázově) s černým překryvem #000000A6
- Stíny: rgba(0,0,0,0.15 až 0.4)
- Poznámka: Elementor výchozí barvy (#6EC1E4, #54595F, #7A7A7A, #61CE70) jsou v kitu definovány, ale na webu se nepoužívají jako značka.

## Písmo
- font-family: "Karla", Sans-serif (Google Fonts, patkové nejsou). Použito všude (nadpisy, menu, tlačítka, text).
- Velikosti: H1 55 px, sekční nadpisy 45 px (600, VERZÁLKY), tlačítka 20 px VERZÁLKY, text 18 px (16 px mobil). Řezy 400/500/600. Tlačítka bez zaoblení (border-radius 0).

## Logo
- https://metropolitnidivadlo.cz/wp-content/uploads/2023/02/MDP_kulate.svg (viewBox 1500x1500)
- Popis: černý kruh, v něm bílé a červené (#E13233) obrysové stylizované písmo (zkratka MDP / název), pod ním druhá řada bílých znaků a tenká červená vodorovná linka (výška 12 z 1500).
- Fotografie: ukázkový obrázek https://metropolitnidivadlo.cz/wp-content/uploads/2024/03/194f1898-77ac-4ddb-8dfd-1424b3aba270-1024x683.jpg (fotka ze souboru). Styl: divadelní inscenační fotky v krajině, tmavé překryvy na slidech, karty s výškou obrázku 320 px, stín karet. Obsahový styl fotek jsem detailně neprohlížel (obrázky nebyly zobrazeny).

## Tón komunikace
- Oslovení na webu: neutrální, spíš neosobní prezentace; kontaktní údaje bez tykání. Pro e-maily doporučeno vykání, formální, vlídné.
- Slogany / hesla: na webu nezjištěn jednotný slogan. Titulky aktualit jsou emotivní („Kytice dobyla Slovensko! Tři města, tři večery, ovace ve stoje“).
- Lexikum: divadelní, kulturní (inscenace, představení, pohádkový muzikál, režie).

## Paleta pro kokpit (WCAG 2.1 AA)
Charakter: černá + bílá + divadelní červená, bez zaoblení nebo s malým (0-4 px), verzálky jen u tlačítek/nadpisů, písmo Karla.

### Světlý režim
| Role | HEX | Použití |
|---|---|---|
| Pozadí | #FFFFFF | hlavní plocha |
| Plocha (karty) | #F7F5F3 | panely |
| Text | #171717 | základní text |
| Text tlumený | #4B4B4B | popisky |
| Akcent (tlačítko / odkaz) | #D5291F | primární tlačítko, bílý text |
| Akcent text (odkazy, malý) | #B3201A | text akcentní barvy |
| Okraj / UI prvek | #8A8A8A | vstupy, ikony, ohraničení |

Kontrasty (spočteno dle WCAG 2.1):
- #171717 na #FFFFFF = 17,93:1; na #F7F5F3 = 16,49:1
- #4B4B4B na #FFFFFF = 8,72:1; na #F7F5F3 = 8,02:1
- #FFFFFF na #D5291F = 5,04:1 (text tlačítka)
- #D5291F na #FFFFFF = 5,04:1; na #F7F5F3 = 4,63:1
- #B3201A na #FFFFFF = 6,69:1; na #F7F5F3 = 6,15:1
- Okraj #8A8A8A na #FFFFFF = 3,45:1; na #F7F5F3 = 3,17:1 (UI ≥ 3:1)
- Pozor: webová #F64A41 na bílé = 3,51:1, na text nestačí; #E13233 na bílé = 4,46:1 (těsně pod 4,5), proto použít #D5291F / #B3201A.

### Tmavý režim
| Role | HEX | Použití |
|---|---|---|
| Pozadí | #0D0D0D | hlavní plocha |
| Plocha (karty) | #171717 | panely |
| Text | #F2F2F2 | základní text |
| Text tlumený | #B8B8B8 | popisky |
| Akcent (odkazy, text) | #FF6B62 | světlejší červená |
| Akcent tlačítka | #F64A41 s textem #0D0D0D | primární tlačítko (barva z webu) |
| Okraj / UI prvek | #767676 | vstupy, ohraničení |

Kontrasty:
- #F2F2F2 na #0D0D0D = 17,36:1; na #171717 = 16,01:1
- #B8B8B8 na #0D0D0D = 9,80:1; na #171717 = 9,04:1
- #FF6B62 na #0D0D0D = 6,97:1; na #171717 = 6,43:1
- #0D0D0D na #F64A41 = 5,53:1 (text tlačítka); #F64A41 na #0D0D0D = 5,53:1, na #171717 = 5,10:1
- Okraj #767676 na #171717 = 3,95:1; na #0D0D0D = 4,54:1 (UI ≥ 3:1). Jemnější #6E6E6E: 3,81:1 na #0D0D0D, 3,52:1 na #171717 (také vyhovuje).
- Poznámka: kontrasty počítány dle vzorce relativní luminance WCAG 2.1; stavy zaměření (focus) nastavit na 2 px obrys #D5291F (světlý) / #FF6B62 (tmavý).
