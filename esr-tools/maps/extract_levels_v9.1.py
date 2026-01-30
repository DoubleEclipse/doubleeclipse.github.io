import csv
import json
import os
import glob
import re

# --- CONFIGURATION ---
BASE_PATH = r"E:\Games\D2RLAN\D2R\Mods\EasternSunLAN\EasternSunLAN.mpq"

PATH_LEVELS = os.path.join(BASE_PATH, "data", "global", "excel", "levels.txt")
DIR_STRINGS = os.path.join(BASE_PATH, "data", "local", "lng", "strings")
PATH_MODINFO = os.path.join(BASE_PATH, "modinfo.json")

OUTPUT_FILE = "esr_data.js"

def get_mod_version():
    """Extracts Mod Version from commented modinfo.json"""
    if not os.path.exists(PATH_MODINFO):
        print(f"Warning: modinfo.json not found at {PATH_MODINFO}")
        return "Unknown"

    try:
        with open(PATH_MODINFO, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"Mod Version:\s*([0-9]+\.[0-9]+\.[0-9]+)", content)
        if match:
            return match.group(1)

    except Exception as e:
        print(f"Error reading modinfo: {e}")

    return "Unknown"


def load_all_strings():
    string_map = {}
    if not os.path.exists(DIR_STRINGS):
        return string_map

    json_files = glob.glob(os.path.join(DIR_STRINGS, "*.json"))
    for jf in json_files:
        try:
            with open(jf, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        key = entry.get("Key")
                        val = entry.get("enUS")
                        if key and val:
                            string_map[key.lower()] = val
        except: pass
    return string_map

def parse_levels():
    if not os.path.exists(PATH_LEVELS):
        print("CRITICAL: levels.txt not found.")
        return

    name_lookup = load_all_strings()
    mod_ver = get_mod_version()
    levels_db = []

    with open(PATH_LEVELS, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)
        
        def get_val(row, col_name, fallback="0"):
            if col_name not in header: return fallback
            idx = header.index(col_name)
            if idx >= len(row): return fallback
            val = row[idx].strip()
            return val if val else fallback

        vis_indices = [header.index(f"Vis{i}") for i in range(8) if f"Vis{i}" in header]

        for row in reader:
            if not row or len(row) < 5 or row[0] == 'Expansion': continue

            try:
                map_id = int(get_val(row, "Id"))
                if map_id <= 0: continue 

                internal_name = get_val(row, "Name")
                string_key = get_val(row, "LevelName")
                real_name = name_lookup.get(string_key.lower(), internal_name)

                act_raw = int(get_val(row, "Act", "0")) + 1
                
                lower_name = real_name.lower()
                is_endgame = ("tier" in lower_name or "void" in lower_name) and "naraku" not in lower_name
                act = 6 if is_endgame else act_raw

                wp_val = get_val(row, "Waypoint", "255")
                has_wp = wp_val != "255" and wp_val != ""

                # Extract Connections (Vis columns)
                neighbors = []
                for idx in vis_indices:
                    if idx < len(row):
                        val = row[idx]
                        if val.isdigit() and int(val) > 0:
                            neighbors.append(int(val))
                
                levels_db.append({
                    "id": map_id,
                    "name": real_name,
                    "act": act,
                    "has_wp": has_wp,
                    "levels": [
                        get_val(row, "MonLvlEx"),      
                        get_val(row, "MonLvlEx(N)"),   
                        get_val(row, "MonLvlEx(H)")    
                    ],
                    "density": get_val(row, "MonDen(H)", get_val(row, "MonDen")),
                    "uniques": get_val(row, "MonUMin(H)", "0") + "-" + get_val(row, "MonUMax(H)", "0"),
                    "neighbors": list(set(neighbors))
                })

            except ValueError: continue

    export_data = {
        "modVersion": mod_ver,
        "levels": levels_db
    }

    js_content = f"const esrData = {json.dumps(export_data, indent=4)};"
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_content)
    
    print(f"Success. Mapped {len(levels_db)} levels. Mod Version found: {mod_ver}")

if __name__ == "__main__":
    parse_levels()