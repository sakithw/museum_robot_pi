# ============================================================
# exhibits.py — Museum Exhibit Database
# ============================================================
# Add or edit exhibits here.
# Each tag_id maps to name + description in EN, SI (Sinhala), TA (Tamil)
#
# To add a new exhibit:
#   1. Add a new entry with the next tag_id
#   2. Fill in name and description in all 3 languages
#   3. Add the nav_goal (x, y, yaw in RADIANS, MAP frame) from your saved map
#      - Drive to the goal during mapping, use /mark_goal/<id> to record it
# ============================================================

# Load saved nav goals (written by flask_api /mark_goal, survive restarts)
def _load_saved_goals():
    try:
        from nav_goals import NAV_GOALS
        return NAV_GOALS
    except Exception:
        return {}

_SAVED = _load_saved_goals()

EXHIBITS = {
    0: {
        "name": {
            "en": "Welcome",
            "si": "සාදරයෙන් පිළිගනිමු",
            "ta": "வரவேற்கிறோம்"
        },
        "description": {
            "en": "Welcome to the museum. I am your autonomous guide. I will take you through "
                  "our fascinating exhibits today. Please follow me.",
            "si": "කෞතුකාගාරයට සාදරයෙන් පිළිගනිමු. මම ඔබේ ස්වයංක්‍රීය මාර්ගෝපදේශකයා වෙමි. "
                  "අද අපගේ ආකර්ශනීය ප්‍රදර්ශනය හරහා ඔබව රැගෙන යන්නෙමි. කරුණාකර මා අනුගමනය කරන්න.",
            "ta": "அருங்காட்சியகத்திற்கு வரவேற்கிறோம். நான் உங்கள் தன்னியக்க வழிகாட்டி. "
                  "இன்று எங்கள் கண்காட்சிகள் வழியாக உங்களை அழைத்துச் செல்வேன். என்னை பின்தொடரவும்."
        },
        "nav_goal": {"x": 0.0, "y": 0.0, "yaw": 0.0}
    },

    1: {
        "name": {
            "en": "Ancient Pottery",
            "si": "පුරාණ මැටි බඳුන්",
            "ta": "பண்டைய மண் பாத்திரங்கள்"
        },
        "description": {
            "en": "This collection of ancient pottery dates back over two thousand years. "
                  "These vessels were used for storing water, grain, and oil by early civilizations "
                  "that thrived in this region.",
            "si": "මෙම පුරාණ මැටි බඳුන් එකතුව වසර දෙදහසකටත් වඩා පැරණිය. "
                  "මෙම භාජන මෙම ප්‍රදේශයේ ජීවත් වූ පුරාණ ශිෂ්ටාචාරයන් විසින් "
                  "ජලය, ධාන්ය සහ තෙල් ගබඩා කිරීමට භාවිතා කරන ලදී.",
            "ta": "இந்த பண்டைய மட்பாண்ட தொகுப்பு இரண்டாயிரம் ஆண்டுகளுக்கும் மேலானது. "
                  "இந்த பாத்திரங்கள் இந்த பகுதியில் வாழ்ந்த ஆரம்பகால நாகரிகங்களால் "
                  "தண்ணீர், தானியங்கள் மற்றும் எண்ணெய் சேமிக்க பயன்படுத்தப்பட்டன."
        },
        # Nav2 goal — set these after checking your map in RViz
        # Use the 2D Goal Pose tool and note the x, y, yaw values
        "nav_goal": {"x": 1.0, "y": 0.5, "yaw": 0.0}
    },

    2: {
        "name": {
            "en": "Royal Regalia",
            "si": "රාජකීය රාජ්‍ය ලාංඡන",
            "ta": "அரச அடையாளங்கள்"
        },
        "description": {
            "en": "The royal regalia on display here belonged to the kingdom that ruled this land "
                  "during the medieval period. The crown and sceptre are crafted from gold "
                  "and adorned with precious gemstones.",
            "si": "මෙහි ප්‍රදර්ශනය කර ඇති රාජකීය ලාංඡන මධ්‍යකාලීන යුගයේ "
                  "මෙම භූමිය පාලනය කළ රාජධානියට අයත් විය. "
                  "කිරුළ සහ රාජදණ්ඩ රන් වලින් සාදා වටිනා මැණික් වලින් සරසා ඇත.",
            "ta": "இங்கே காட்சிப்படுத்தப்படும் அரச அடையாளங்கள் இடைக்கால காலகட்டத்தில் "
                  "இந்த நிலத்தை ஆண்ட இராச்சியத்திற்கு சொந்தமானவை. "
                  "கிரீடமும் செங்கோலும் தங்கத்தால் செய்யப்பட்டு விலைமதிப்பற்ற கற்களால் அலங்கரிக்கப்பட்டுள்ளன."
        },
        "nav_goal": {"x": 2.5, "y": 1.0, "yaw": 1.57}
    },

    3: {
        "name": {
            "en": "Ancient Weapons",
            "si": "පුරාණ අවි ආයුධ",
            "ta": "பண்டைய ஆயுதங்கள்"
        },
        "description": {
            "en": "This exhibit showcases weapons used by ancient warriors of this region. "
                  "The swords, spears, and shields on display demonstrate the advanced "
                  "metallurgical skills of ancient craftsmen.",
            "si": "මෙම ප්‍රදර්ශනය මෙම ප්‍රදේශයේ පුරාණ යෝධයන් විසින් භාවිතා කළ "
                  "අවි ආයුධ ප්‍රදර්ශනය කරයි. ප්‍රදර්ශනය කර ඇති කඩු, හෙල්ල සහ පලිහ "
                  "පුරාණ ශිල්පීන්ගේ උසස් ලෝහකාර්ම කුසලතා පෙන්නුම් කරයි.",
            "ta": "இந்த கண்காட்சி இந்த பகுதியின் பண்டைய போர்வீரர்கள் பயன்படுத்திய "
                  "ஆயுதங்களை காட்சிப்படுத்துகிறது. காட்சிப்படுத்தப்படும் வாள்கள், "
                  "ஈட்டிகள் மற்றும் கேடயங்கள் பண்டைய கைவினைஞர்களின் உன்னத உலோகவியல் திறன்களை நிரூபிக்கின்றன."
        },
        "nav_goal": {"x": 3.0, "y": 2.5, "yaw": 3.14}
    },

    4: {
        "name": {
            "en": "Traditional Textiles",
            "si": "සාම්ප්‍රදායික රෙදිපිළි",
            "ta": "பாரம்பரிய ஜவுளிகள்"
        },
        "description": {
            "en": "The traditional textiles in this collection represent centuries of weaving "
                  "craftsmanship. Each pattern tells a story of cultural identity and the "
                  "rich heritage of the people of this land.",
            "si": "මෙම එකතුවේ සාම්ප්‍රදායික රෙදිපිළි සියවස් ගණනාවක් පුරා "
                  "වියන ශිල්පකාර්මය නියෝජනය කරයි. එක් එක් රටාව මෙම භූමියේ "
                  "ජනතාවගේ සංස්කෘතික අනන්‍යතාවය සහ සොඳුරු උරුමය පිළිබඳ කතාවක් කියයි.",
            "ta": "இந்த தொகுப்பின் பாரம்பரிய ஜவுளிகள் நூற்றாண்டுகளான நெசவு கைவினை திறனை "
                  "பிரதிநிதித்துவப்படுத்துகின்றன. ஒவ்வொரு வடிவமும் இந்த நிலத்தின் மக்களின் "
                  "கலாச்சார அடையாளம் மற்றும் செழிப்பான பாரம்பரியம் பற்றிய கதையை சொல்கிறது."
        },
        "nav_goal": {"x": 1.5, "y": 3.5, "yaw": -1.57}
    },

    5: {
        "name": {
            "en": "Ancient Coins",
            "si": "පුරාණ කාසි",
            "ta": "பண்டைய நாணயங்கள்"
        },
        "description": {
            "en": "This remarkable collection of ancient coins spans over fifteen centuries "
                  "of trade and commerce. The coins reveal the extensive trade networks "
                  "that connected this island to distant lands across the Indian Ocean.",
            "si": "පුරාණ කාසිවල මෙම විශිෂ්ට එකතුව වාණිජ්‍යයේ සියවස් පහළොවකට "
                  "වැඩි කාලයක් ආවරණය කරයි. කාසි මෙම දූපත ඉන්දියන් සාගරය හරහා "
                  "දුරස්ථ භූමිවලට සම්බන්ධ කළ පුළුල් වෙළඳ ජාල අනාවරණය කරයි.",
            "ta": "பண்டைய நாணயங்களின் இந்த குறிப்பிடத்தக்க தொகுப்பு பதினைந்து நூற்றாண்டுகளுக்கும் "
                  "மேலான வர்த்தகத்தை உள்ளடக்கியது. நாணயங்கள் இந்தத் தீவை இந்தியப் பெருங்கடல் "
                  "வழியாக தொலைதூர நிலங்களுடன் இணைத்த விரிவான வர்த்தக நெட்வொர்க்குகளை வெளிப்படுத்துகின்றன."
        },
        "nav_goal": {"x": 0.5, "y": 4.0, "yaw": 0.0}
    }
}

# Overlay saved goals (map frame, radians) over the hardcoded defaults
for _tid, _goal in _SAVED.items():
    if _tid in EXHIBITS:
        EXHIBITS[_tid]['nav_goal'] = _goal
