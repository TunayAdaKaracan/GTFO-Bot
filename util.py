TIME_UNITS = {
    "sn": 1,
    "saniye": 1,
    "dk": 60,
    "dakika": 60,
    "s": 60 * 60,
    "saat": 60 * 60,
    "gn": 60 * 60 * 24,
    "gün": 60 * 60 * 24
}

INTEGERS = "0123456789"


def parseDate(text):
    time = ""
    unit = ""
    total = 0
    for char in text:
        if char in "    \t":
            if unit not in TIME_UNITS:
                return None, f"{time if unit == '' else unit} geçerli bir zaman birimi değil!"
            total += TIME_UNITS[unit] * int(time)
            unit = ""
            time = ""
            continue

        if char in INTEGERS and unit == "":
            time += char
        elif char not in INTEGERS and time != "":
            unit += char
        elif char not in INTEGERS and time == "":
            return None, "Zaman birimi için herhangi bir sayı vermediniz!"
        elif char in INTEGERS and unit != "":
            if unit not in TIME_UNITS:
                return None, f"{time if unit == '' else unit} geçerli bir zaman birimi değil!"
            total += TIME_UNITS[unit] * int(time)
            unit = ""
            time = "" + char

    if unit not in TIME_UNITS:
        return None, f"{time if unit == '' else unit} geçerli bir zaman birimi değil!"
    total += TIME_UNITS[unit] * int(time)

    return total, None


class State:
    def __init__(self, id, desc, emoji):
        self.id = id
        self.desc = desc
        self.emoji = emoji

    def __repr__(self):
        return f"State ID={self.id} Desc={self.desc}"


class RoomStates:
    ACTIVE = State(0, "Oda aktif.", "<:aktif:1061598738562437210>")
    FULL = State(1, "Oda dolu.", "<:dolu:1061598742932889630>")
    DEAD = State(2, "Oyun başladı", "<:devamediyor:1061598741209022464>")

    @staticmethod
    def fromId(id):
        for name in dir(RoomStates):
            if not name.startswith("__"):
                val = getattr(RoomStates, name)
                valid = getattr(val, "id", None)
                if valid == id:
                    return val
        return None