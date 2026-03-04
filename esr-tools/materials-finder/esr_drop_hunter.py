import csv
import re
import os
import json

# ==========================================
# CONFIGURATION
# ==========================================
DATA_PATH = r"E:\Games\D2RLAN\D2R\Mods\EasternSunLAN\EasternSunLAN.mpq\data\global\excel"
OUTPUT_JS_FILE = "drop_data.js"

# Fallback codes
KNOWN_CODES = {
    "Heart": "hrt", "Brain": "brz", "Jawbone": "jaw", "Eye": "eyz", 
    "Horn": "hrn", "Tail": "tal", "Flag": "flg", "Fang": "fng", 
    "Quill": "qll", "Soul": "sol", "Scalp": "scz", "Spleen": "spe", 
    "Steak": "zzz",
    "Decipherer": "ddd", "Dragon Stone": "ppp", "Cook Book": "yyy", 
    "Anvil Stone": "qqq", "Socket Donut": "sdo", "Elixir": "elx",
    "Worldstone Shard": "wss", "Ore": "ore", "Maple Leaf": "map"
}

def clean_str(s):
    if not s: return ""
    return s.strip().lower().replace(" ", "")

def load_item_codes(path):
    file_path = os.path.join(path, "misc.txt")
    if os.path.exists(file_path):
        print(f"Reading {file_path}...")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    name = row.get('name', '').strip()
                    code = row.get('code', '').strip()
                    for target in KNOWN_CODES.keys():
                        if target.lower().replace(" ","") == name.lower().replace(" ",""):
                            KNOWN_CODES[target] = code
        except: pass
    return KNOWN_CODES

def build_tc_chain(path, target_item_codes):
    file_path = os.path.join(path, "TreasureClassEx.txt")
    if not os.path.exists(file_path): return {}
    print(f"Analyzing Treasure Classes...")
    tc_data = {}
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                tc_name = row.get('Treasure Class', '')
                if not tc_name: continue
                drops = []
                for i in range(1, 11): 
                    val = row.get(f'Item{i}', '').strip()
                    if val: drops.append(val)
                tc_data[tc_name] = drops
    except: return {}

    tc_contains_target = {tc: set() for tc in tc_data}
    target_vals = list(target_item_codes.values())

    for _ in range(5):
        for tc, drops in tc_data.items():
            for drop in drops:
                if drop in target_vals:
                    tc_contains_target[tc].add(drop)
                elif drop in tc_contains_target:
                    tc_contains_target[tc].update(tc_contains_target[drop])
    return {k: list(v) for k, v in tc_contains_target.items() if v}

def scan_monsters(path, item_map, valid_tcs):
    grouped_mobs = {} 
    file_path = os.path.join(path, "monstats.txt")
    print(f"Scanning Monsters...")
    
    tc_cols = {
        'Normal': ['TreasureClass1', 'TreasureClass2', 'TreasureClass3', 'TreasureClass4'],
        'Nightmare': ['TreasureClass1(N)', 'TreasureClass2(N)', 'TreasureClass3(N)', 'TreasureClass4(N)'],
        'Hell': ['TreasureClass1(H)', 'TreasureClass2(H)', 'TreasureClass3(H)', 'TreasureClass4(H)']
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                mon_id = row.get('Id', '')
                if not mon_id or mon_id == 'Expansion': continue
                
                # BaseId helps grouping (e.g. "Fallen1" -> Fallen)
                # But to list "Families", we want the NameStr
                base_id = row.get('BaseId', mon_id) or mon_id
                mon_name = row.get('NameStr', mon_id)

                drops_found = []
                for diff, cols in tc_cols.items():
                    for col in cols:
                        tc_val = row.get(col, '')
                        if not tc_val: continue
                        
                        for name, code in item_map.items():
                            if re.search(r'\b' + re.escape(code) + r'\b', tc_val, re.IGNORECASE):
                                drops_found.append((name, diff))
                        
                        if tc_val in valid_tcs:
                            for code in valid_tcs[tc_val]:
                                name = next((n for n, c in item_map.items() if c == code), None)
                                if name: drops_found.append((name, diff))
                                
                if drops_found:
                    if base_id not in grouped_mobs:
                        grouped_mobs[base_id] = {'Name': mon_name, 'Members': {}}
                    grouped_mobs[base_id]['Members'][mon_id] = {
                        'SpecificName': mon_name,
                        'Drops': drops_found
                    }
    except: pass
    return grouped_mobs

def map_levels(path, mon_ids):
    locs = {mid: {'Normal': [], 'Nightmare': [], 'Hell': []} for mid in mon_ids}
    file_path = os.path.join(path, "levels.txt")
    print(f"Mapping Levels...")
    
    spawn_cols = {
        'Normal': [f"mon{i}" for i in range(1, 26)],
        'Nightmare': [f"nmon{i}" for i in range(1, 26)],
        'Hell': [f"umon{i}" for i in range(1, 26)] 
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                lvl_name = row.get('LevelName', '')
                if not lvl_name: continue
                
                try: lvl_id = int(row.get('Id', 999))
                except: lvl_id = 999
                
                try: act = int(row.get('Act', 0)) + 1
                except: act = 1

                for diff, cols in spawn_cols.items():
                    for col in cols:
                        mid = row.get(col, '')
                        if mid in locs:
                            if not any(l['m'] == lvl_name for l in locs[mid][diff]):
                                locs[mid][diff].append({'m': lvl_name, 'a': act, 'lid': lvl_id})
    except: pass
    return locs

def generate_js(grouped_mobs, locs):
    print("Consolidating Data...")
    
    # Structure: (Item, Diff, Act, Map, LvlID) -> Set of FamilyNames
    final_data_map = {}

    for base_id, family in grouped_mobs.items():
        family_name = family['Name'] 
        
        for mon_id, mon_data in family['Members'].items():
            
            for (item, diff) in mon_data['Drops']:
                
                places = locs.get(mon_id, {}).get(diff, [])
                if not places:
                    # Boss/Summon/Special - ID 999 puts it at end of list
                    places = [{'m': 'Boss / Summon / Special', 'a': 0, 'lid': 999}]

                for p in places:
                    key = (item, diff, p['a'], p['m'], p['lid'])
                    if key not in final_data_map:
                        final_data_map[key] = set()
                    final_data_map[key].add(family_name)

    # Convert to list for JS
    export_data = []
    for (item, diff, act, map_name, lvl_id), families in final_data_map.items():
        fam_list = sorted(list(families))
        
        # JOIN ALL FAMILIES (No Truncation)
        fam_str = ", ".join(fam_list)

        export_data.append({
            "i": item,      # Item
            "d": diff,      # Difficulty
            "a": act,       # Act
            "m": map_name,  # Map
            "id": lvl_id,   # Level ID (Sort Key)
            "f": fam_str,   # Families
            "s": ""         # (Unused field kept for structure consistency if needed later)
        })

    print(f"Writing {OUTPUT_JS_FILE}...")
    json_str = json.dumps(export_data)
    with open(OUTPUT_JS_FILE, "w", encoding="utf-8") as f:
        f.write(f"const DROP_DATA = {json_str};")
    print("Done.")

if __name__ == "__main__":
    if not os.path.exists(DATA_PATH):
        print(f"CRITICAL: Path {DATA_PATH} does not exist.")
    else:
        codes = load_item_codes(DATA_PATH)
        valid_tcs = build_tc_chain(DATA_PATH, codes)
        mobs = scan_monsters(DATA_PATH, codes, valid_tcs)
        all_ids = []
        for f in mobs.values(): all_ids.extend(f['Members'].keys())
        locs = map_levels(DATA_PATH, all_ids)
        generate_js(mobs, locs)