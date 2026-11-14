"""
Where is a story about? Finds a country (with its flag) and, for Sri Lanka, a town or district.
Used when the AI did not give a place, e.g. for headline-only stories.
"""

import re

# country name (and common words that mean it) -> ISO code, used to make the flag
COUNTRIES = {
    "Sri Lanka": ("LK", ["sri lanka", "sri lankan", "lanka"]),
    "India": ("IN", ["india", "indian", "new delhi", "mumbai", "chennai", "tamil nadu", "modi"]),
    "Pakistan": ("PK", ["pakistan", "pakistani", "islamabad", "karachi", "lahore"]),
    "Bangladesh": ("BD", ["bangladesh", "bangladeshi", "dhaka"]),
    "Maldives": ("MV", ["maldives", "maldivian"]),
    "Nepal": ("NP", ["nepal", "nepali", "kathmandu"]),
    "Afghanistan": ("AF", ["afghanistan", "afghan", "kabul", "taliban"]),
    "China": ("CN", ["china", "chinese", "beijing", "shanghai", "xi jinping"]),
    "Japan": ("JP", ["japan", "japanese", "tokyo"]),
    "South Korea": ("KR", ["south korea", "south korean", "seoul"]),
    "North Korea": ("KP", ["north korea", "north korean", "pyongyang"]),
    "Taiwan": ("TW", ["taiwan", "taiwanese", "taipei"]),
    "Hong Kong": ("HK", ["hong kong"]),
    "Singapore": ("SG", ["singapore"]),
    "Malaysia": ("MY", ["malaysia", "malaysian", "kuala lumpur"]),
    "Indonesia": ("ID", ["indonesia", "indonesian", "jakarta", "bali"]),
    "Thailand": ("TH", ["thailand", "thai", "bangkok"]),
    "Vietnam": ("VN", ["vietnam", "vietnamese", "hanoi"]),
    "Philippines": ("PH", ["philippines", "philippine", "filipino", "manila"]),
    "Myanmar": ("MM", ["myanmar", "burma", "yangon"]),
    "Cambodia": ("KH", ["cambodia", "cambodian", "phnom penh"]),
    "Australia": ("AU", ["australia", "australian", "sydney", "melbourne", "canberra"]),
    "New Zealand": ("NZ", ["new zealand", "auckland", "wellington"]),
    "United States": ("US", ["united states", "u.s.", "us president", "american", "washington", "new york", "brooklyn",
                             "california", "texas", "florida", "white house", "trump", "pentagon", "congress", "senate"]),
    "Canada": ("CA", ["canada", "canadian", "ottawa", "toronto"]),
    "Mexico": ("MX", ["mexico", "mexican"]),
    "Brazil": ("BR", ["brazil", "brazilian", "rio de janeiro", "sao paulo"]),
    "Argentina": ("AR", ["argentina", "argentine", "buenos aires"]),
    "Venezuela": ("VE", ["venezuela", "venezuelan", "caracas"]),
    "Colombia": ("CO", ["colombia", "colombian", "bogota"]),
    "Chile": ("CL", ["chile", "chilean"]),
    "Peru": ("PE", ["peru", "peruvian"]),
    "Cuba": ("CU", ["cuba", "cuban", "havana"]),
    "United Kingdom": ("GB", ["united kingdom", "britain", "british", "england", "scotland", "wales", "london", "uk "]),
    "Ireland": ("IE", ["ireland", "irish", "dublin"]),
    "France": ("FR", ["france", "french", "paris", "macron"]),
    "Germany": ("DE", ["germany", "german", "berlin"]),
    "Italy": ("IT", ["italy", "italian", "rome", "milan"]),
    "Spain": ("ES", ["spain", "spanish", "madrid", "barcelona"]),
    "Portugal": ("PT", ["portugal", "portuguese", "lisbon"]),
    "Netherlands": ("NL", ["netherlands", "dutch", "amsterdam"]),
    "Belgium": ("BE", ["belgium", "belgian", "brussels"]),
    "Switzerland": ("CH", ["switzerland", "swiss", "geneva", "zurich"]),
    "Austria": ("AT", ["austria", "austrian", "vienna"]),
    "Sweden": ("SE", ["sweden", "swedish", "stockholm"]),
    "Norway": ("NO", ["norway", "norwegian", "oslo"]),
    "Denmark": ("DK", ["denmark", "danish", "copenhagen", "greenland"]),
    "Finland": ("FI", ["finland", "finnish", "helsinki"]),
    "Poland": ("PL", ["poland", "polish", "warsaw"]),
    "Ukraine": ("UA", ["ukraine", "ukrainian", "kyiv", "kiev", "zelensky", "zelenskyy"]),
    "Russia": ("RU", ["russia", "russian", "moscow", "kremlin", "putin"]),
    "Belarus": ("BY", ["belarus"]),
    "Greece": ("GR", ["greece", "greek", "athens"]),
    "Turkey": ("TR", ["turkey", "turkish", "türkiye", "ankara", "istanbul", "erdogan"]),
    "Hungary": ("HU", ["hungary", "hungarian", "budapest"]),
    "Romania": ("RO", ["romania", "romanian"]),
    "Serbia": ("RS", ["serbia", "serbian", "belgrade"]),
    "Albania": ("AL", ["albania", "albanian", "tirana"]),
    "Israel": ("IL", ["israel", "israeli", "jerusalem", "tel aviv", "netanyahu"]),
    "Palestine": ("PS", ["palestine", "palestinian", "gaza", "west bank", "hamas"]),
    "Lebanon": ("LB", ["lebanon", "lebanese", "beirut", "hezbollah"]),
    "Syria": ("SY", ["syria", "syrian", "damascus"]),
    "Iraq": ("IQ", ["iraq", "iraqi", "baghdad"]),
    "Iran": ("IR", ["iran", "iranian", "tehran"]),
    "Saudi Arabia": ("SA", ["saudi arabia", "saudi", "riyadh"]),
    "UAE": ("AE", ["united arab emirates", "uae", "dubai", "abu dhabi"]),
    "Qatar": ("QA", ["qatar", "qatari", "doha"]),
    "Kuwait": ("KW", ["kuwait"]),
    "Bahrain": ("BH", ["bahrain", "bahraini", "manama"]),
    "Oman": ("OM", ["oman", "omani", "muscat"]),
    "Yemen": ("YE", ["yemen", "yemeni", "houthi"]),
    "Jordan": ("JO", ["jordan", "jordanian", "amman"]),
    "Egypt": ("EG", ["egypt", "egyptian", "cairo"]),
    "Libya": ("LY", ["libya", "libyan", "tripoli"]),
    "Sudan": ("SD", ["sudan", "sudanese", "khartoum"]),
    "Ethiopia": ("ET", ["ethiopia", "ethiopian", "addis ababa"]),
    "Kenya": ("KE", ["kenya", "kenyan", "nairobi"]),
    "Nigeria": ("NG", ["nigeria", "nigerian", "lagos", "abuja"]),
    "Ghana": ("GH", ["ghana", "ghanaian"]),
    "South Africa": ("ZA", ["south africa", "south african", "johannesburg", "cape town"]),
    "Somalia": ("SO", ["somalia", "somali", "mogadishu"]),
    "Congo": ("CD", ["congo", "kinshasa"]),
    "Morocco": ("MA", ["morocco", "moroccan"]),
    "Algeria": ("DZ", ["algeria", "algerian"]),
    "Tunisia": ("TN", ["tunisia", "tunisian"]),
}

SRI_LANKA_PLACES = [
    "Colombo", "Wellawatte", "Bambalapitiya", "Kollupitiya", "Pettah", "Borella", "Maradana", "Dehiwala",
    "Mount Lavinia", "Moratuwa", "Kotte", "Battaramulla", "Nugegoda", "Maharagama", "Kaduwela", "Kelaniya",
    "Gampaha", "Negombo", "Katunayake", "Ja-Ela", "Wattala", "Kalutara", "Panadura", "Beruwala",
    "Kandy", "Matale", "Nuwara Eliya", "Hatton", "Galle", "Matara", "Hambantota", "Tangalle",
    "Jaffna", "Kilinochchi", "Mannar", "Vavuniya", "Mullaitivu", "Trincomalee", "Batticaloa", "Ampara",
    "Kurunegala", "Puttalam", "Chilaw", "Anuradhapura", "Polonnaruwa", "Badulla", "Bandarawela",
    "Monaragala", "Ratnapura", "Kegalle", "Avissawella", "Embilipitiya", "Dambulla", "Sigiriya", "Hikkaduwa",
    "Unawatuna", "Mirissa", "Arugam Bay", "Kalmunai", "Point Pedro", "Mihintale",
]

# order matters: check longer / more specific names first
_ALIASES = sorted(((alias, name) for name, (_, aliases) in COUNTRIES.items() for alias in aliases),
                  key=lambda x: -len(x[0]))


def flag(country):
    code = COUNTRIES.get(country, ("",))[0]
    if len(code) != 2:
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


def find_countries(text):
    """All countries mentioned, in the order they appear."""
    t = " " + re.sub(r"[^\w.\s'-]", " ", text.lower()) + " "
    found = {}
    m = re.search(r"\b(US|USA|U\.S\.?)\b", text)   # capital "US" only, so the word "us" doesn't count
    if m:
        found["United States"] = m.start() + 1
    for alias, name in _ALIASES:
        m = re.search(r"(?<![\w])" + re.escape(alias.strip()) + r"(?![\w])", t)
        if m and (name not in found or m.start() < found[name]):
            found[name] = m.start()
    return [n for n, _ in sorted(found.items(), key=lambda x: x[1])]


def find_country(text):
    c = find_countries(text)
    return c[0] if c else ""


# words that show a story from a Sri Lankan outlet really is about Sri Lanka
SL_SIGNALS = re.compile(r"\b(parliament|cabinet|president|prime minister|minister|ministry|budget|rupee|cbsl|central bank|"
                        r"police|court|provincial|district|divisional|government|govt|election|opposition|npp|sjb|slpp|unp|"
                        r"a/l|o/l|exam|thero|kovil|tea|paddy|irrigation|dmc|met department|pradeshiya|grama|"
                        r"colombo stock|cse|ceylon|lankan?)\b", re.I)


def find_sl_place(text):
    for p in sorted(SRI_LANKA_PLACES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(p) + r"\b", text):
            return p
    return ""


def location_for(story, cards=None):
    """Returns {"country": ..., "place": ..., "flag": ...} or {} if unknown. Never guesses beyond the text."""
    cards = cards or {}
    country = (cards.get("country") or "").strip()
    place = (cards.get("place") or "").strip()
    text = story["title"] + " " + story.get("summary", "")
    if country and country not in COUNTRIES:
        country = find_country(country) or country  # e.g. "the US" -> United States
    others = []
    if not country:
        found = find_countries(story["title"]) or find_countries(text)
        if found:
            country, others = found[0], found[1:3]
    if not country and story.get("region") == "sri_lanka":
        # a Sri Lankan outlet: only call it Sri Lanka if the text shows a Sri Lankan sign
        if find_sl_place(text) or SL_SIGNALS.search(text):
            country = "Sri Lanka"
    if not place and country == "Sri Lanka":
        place = find_sl_place(text)
    if place and country and place.lower() == country.lower():
        place = ""
    if not country and not place:
        return {}
    loc = {"country": country, "place": place, "flag": flag(country) if country else "📍"}
    if others and not place:
        loc["also"] = others
        loc["flag"] = " ".join(flag(c) for c in [country] + others)
    return loc


def label(loc, short=False):
    if not loc:
        return ""
    if loc.get("also"):
        return " / ".join([loc["country"]] + loc["also"])
    if loc.get("place") and loc.get("country"):
        return f"{loc['place']}, {loc['country']}"
    return loc.get("place") or loc.get("country", "")
