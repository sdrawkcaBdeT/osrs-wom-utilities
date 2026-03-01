from datetime import datetime, timezone

BANNED_ACCOUNTS_CT: dict[str, str] = {
    "BISKIEZ209": "2026/02/09 07:27",
    "frostytimez": "2026/02/09 07:28",
    "Touroshui": "2026/01/29 04:58",
    "corssMi11": "2026/01/27 11:12",
    "geensliyh": "2026/01/16 09:13",
    "gigidere": "2026/02/09 07:28",
    "triunhiji": "2026/02/08 07:53",
    "RogueStride": "2026/02/09 07:28",
    "Nnelg147": "2026/02/05 05:57",
    "pxncrasia": "2026/02/09 07:29",
    "D0m1n09": "2026/02/09 07:29",
    "Rockangel205": "2026/02/09 07:29",
    "anstinine": "2026/01/29 02:51",
    "Atrelnwor": "2026/01/20 08:05",
    "Stigitch": "2026/02/09 07:29",
    "WhitePriest9": "2026/02/09 07:29",
    "rizzlomidezz": "2026/02/03 11:06",
    "fer8m3r": "2026/02/05 05:58",
    "Zetaqoo": "2026/02/09 07:30",
    "Soulsmith40": "2026/02/05 05:59",
    "Camerm97": "2026/02/09 07:30",
    "ClourTroth": "2026/02/09 07:30",
    "Obida134": "2026/02/09 07:30",
    "DarkRaptor98": "2026/02/09 07:30",
    "Rawta123": "2026/02/09 07:30",
    "Wishful Qrow": "2026/02/09 07:30",
    "nighteagle1": "2026/02/05 05:59",
    "Kleiberpro25": "2026/02/09 07:30",

    "iBuul": "2026/02/18 00:00",
    "NightTraceur": "2026/02/18 00:00",
}

# Note: As-of 2026/02/18, I've tracked 30 accounts, and of those 30, 28 have been banned.
# That's a 93.33% success rate at identifying bots. Or when I think someone is a bot, they are. 
# Some might slip by still. Especially the scrambler bots.