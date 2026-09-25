"""
Low-level parser module for extracting metadata from PlayStation PKG containers (PS5 & PS4).
Features robust fallback mechanisms for Delta Patches, Backports, and modded FPKGs.
"""
import os
import struct
import json
import hashlib
import re
from logger import logger

ICONS_DIR = os.path.join(os.path.dirname(__file__), 'icons')
if not os.path.exists(ICONS_DIR):
    os.makedirs(ICONS_DIR)

def format_size(file_size):
    if not file_size or file_size < 0:
        return "0 B"
    if file_size < 1024:
        return f"{file_size} B"
    elif file_size < 1024**2:
        return f"{round(file_size / 1024, 1)} KB"
    elif file_size < 1024**3:
        return f"{round(file_size / (1024**2), 1)} MB"
    else:
        return f"{round(file_size / (1024**3), 2)} GB"

def create_error_entry(pkg_path, file_size, error_msg):
    path_hash = hashlib.md5(pkg_path.encode('utf-8')).hexdigest()
    unique_id = f"ERR_{path_hash[:8]}"
    return {
        "catalog": {
            "id": unique_id,
            "title": os.path.basename(pkg_path),
            "titleId": "ERROR",
            "version": "—",
            "size": file_size,
            "sizeText": format_size(file_size),
            "role": "Error",
            "familyKey": "ERROR",
            "platform": "N/A",
            "format": "pkg",
            "file": os.path.basename(pkg_path),
            "originalFilename": os.path.basename(pkg_path),
            "fullPath": pkg_path,
            "hasIcon": False,
            "error": error_msg
        },
        "local_pkg": pkg_path,
        "local_icon": ""
    }

def parse_sfo(sfo_bytes):
    if len(sfo_bytes) < 20 or sfo_bytes[:4] != b'\x00PSF':
        return None
    try:
        key_table_offset, data_table_offset, entry_count = struct.unpack_from("<III", sfo_bytes, 0x08)
        info = {}
        for i in range(entry_count):
            key_off, fmt, length, max_len, data_off = struct.unpack_from("<HHIII", sfo_bytes, 0x14 + i * 16)
            key_end = sfo_bytes.find(b'\x00', key_table_offset + key_off)
            if key_end == -1:
                continue
            key = sfo_bytes[key_table_offset + key_off : key_end].decode('utf-8', errors='ignore')
            data_start = data_table_offset + data_off
            
            if fmt == 0x0204:
                val = sfo_bytes[data_start : data_start + length].split(b'\x00')[0].decode('utf-8', errors='ignore')
            elif fmt == 0x0404:
                val = struct.unpack_from("<I", sfo_bytes, data_start)[0]
            else:
                val = None
            if val is not None:
                info[key] = val
        return info
    except Exception as e:
        logger.warning(f"SFO parsing warning: {str(e)}")
        return None

def extract_ps5_title(parsed_json, original_name):
    localized = parsed_json.get("localizedParameters", {})
    if localized:
        default_lang = localized.get("defaultLanguage")
        if default_lang and default_lang in localized:
            title = localized[default_lang].get("titleName")
            if title:
                return title
        
        for fallback in ["ru-RU", "en-US", "en-GB"]:
            if fallback in localized and localized[fallback].get("titleName"):
                return localized[fallback].get("titleName")
            
        for lang_data in localized.values():
            if isinstance(lang_data, dict) and lang_data.get("titleName"):
                return lang_data.get("titleName")
                
    return parsed_json.get("titleName", original_name)

def guess_metadata_from_path(pkg_path, content_id=""):
    """
    Эвристический поиск названия, TitleID, версии и типа (Patch/Game/DLC)
    для нестандартных пакетов (Delta Backports, модифицированные патчи).
    """
    fname = os.path.basename(pkg_path)
    parent_dir = os.path.basename(os.path.dirname(pkg_path))
    grandparent_dir = os.path.basename(os.path.dirname(os.path.dirname(pkg_path)))
    full_str = f"{grandparent_dir} {parent_dir} {fname} {content_id}"

    # Поиск Title ID (PPSAxxxxx или CUSAxxxxx)
    m_id = re.search(r'([CP][UP][S][A-Z]\d{5})', full_str, re.IGNORECASE)
    title_id = m_id.group(1).upper() if m_id else "UNKNOWN"

    # Определение платформы
    if title_id.startswith("PPSA") or "ps5" in full_str.lower():
        platform = "PS5"
    elif title_id.startswith("CUSA"):
        platform = "PS4"
    else:
        platform = "PS5"

    # Определение роли
    fl = full_str.lower()
    if any(k in fl for k in ["backport", "backpork", "patch", "update", "bp4", "bp5", "fullrus", "v1.", "v01."]):
        role = "Patch"
    elif any(k in fl for k in ["dlc", "bonus", "pre-order", "preorder", "addon", "extra"]):
        role = "DLC"
    else:
        role = "Game"

    # Определение версии
    m_ver = re.search(r'v(\d+\.\d+(\.\d+)?)', full_str, re.IGNORECASE)
    version = m_ver.group(1) if m_ver else "1.00"

    # Формирование читаемого названия
    title_name = fname
    for part in [parent_dir, grandparent_dir]:
        clean_name = re.sub(r'\[.*?\]|\(.*?\)', '', part).strip(' -_')
        if clean_name and len(clean_name) > 3 and not clean_name.lower().startswith("up") and not clean_name.lower().startswith("ppsa"):
            title_name = clean_name
            break

    return title_id, title_name, platform, role, version

def extract_pkg_meta(pkg_path):
    file_size = 0
    try:
        file_size = os.path.getsize(pkg_path)
        if file_size < 2000:
            msg = f"File too small ({file_size} bytes)"
            logger.warning(f"PKG {pkg_path}: {msg}")
            return create_error_entry(pkg_path, file_size, msg)

        with open(pkg_path, 'rb') as f:
            magic = f.read(4)
            cnt_offset = 0
            platform = "PS4"
            content_id = ""

            if magic == b'\x7FFIH':
                platform = "PS5"
                f.seek(0x58)
                ptr_data = f.read(8)
                if len(ptr_data) < 8:
                    logger.warning(f"PKG {pkg_path}: Failed to read FIH pointer table at 0x58")
                else:
                    cnt_offset = struct.unpack("<Q", ptr_data)[0]
            elif magic == b'\x7FCNT':
                cnt_offset = 0
                platform = "PS4"
            else:
                logger.warning(f"PKG {pkg_path}: Unknown container magic [{magic.hex()}]. Attempting heuristic fallback.")
                tid, tname, plat, rle, ver = guess_metadata_from_path(pkg_path)
                if tid != "UNKNOWN":
                    path_hash = hashlib.md5(pkg_path.encode('utf-8')).hexdigest()
                    unique_id = f"{tid}_{path_hash[:6]}"
                    logger.info(f"Heuristically recovered PKG metadata for {tname} ({tid}) as {plat} {rle} v{ver}")
                    return {
                        "catalog": {
                            "id": unique_id,
                            "title": tname,
                            "titleId": tid,
                            "version": ver,
                            "size": file_size,
                            "sizeText": format_size(file_size),
                            "role": rle,
                            "familyKey": tid,
                            "platform": plat,
                            "format": "pkg",
                            "file": f"{unique_id}.pkg",
                            "originalFilename": os.path.basename(pkg_path),
                            "fullPath": pkg_path,
                            "hasIcon": False,
                            "error": False
                        },
                        "local_pkg": pkg_path,
                        "local_icon": ""
                    }
                return create_error_entry(pkg_path, file_size, f"Unknown magic [{magic.hex()}]")

            if cnt_offset >= file_size or cnt_offset < 0:
                logger.warning(f"PKG {pkg_path}: Corrupted CNT pointer: {cnt_offset}")
                cnt_offset = 0

            # Попытка прочесть Content ID из заголовка (смещение 0x40 от начала CNT)
            try:
                f.seek(cnt_offset + 0x40)
                cid_raw = f.read(48).split(b'\x00')[0]
                content_id = cid_raw.decode('utf-8', errors='ignore').strip()
            except Exception:
                content_id = ""

            f.seek(cnt_offset + 0x10)
            header_data = f.read(12)
            if len(header_data) < 12:
                logger.warning(f"PKG {pkg_path}: EOF in CNT header at offset {cnt_offset + 0x10}")
                entry_count = 0
                entry_table_offset = 0
            else:
                entry_count = struct.unpack(">I", header_data[0:4])[0]
                entry_table_offset = cnt_offset + struct.unpack(">I", header_data[8:12])[0]

            sfo_info = json_info = icon_data = None

            if 0 < entry_count <= 20000 and entry_table_offset < file_size:
                table_size_bytes = entry_count * 32
                f.seek(entry_table_offset)
                entry_table = f.read(table_size_bytes)
                
                for i in range(entry_count):
                    entry = entry_table[i*32 : (i+1)*32]
                    if len(entry) < 32:
                        break
                    e_id, _, _, _, e_off, e_size, _ = struct.unpack(">IIIIIIQ", entry)
                    
                    target_offset = cnt_offset + e_off
                    if target_offset + e_size > file_size:
                        if e_off + e_size <= file_size:
                            target_offset = e_off
                        else:
                            continue
                    
                    if e_id == 0x1000:
                        sfo_info = {"offset": target_offset, "size": e_size}
                    elif e_id in (0x2000, 0x1008):
                        json_info = {"offset": target_offset, "size": e_size}
                    elif e_id == 0x1200:
                        icon_data = {"offset": target_offset, "size": e_size}

            title_id = "UNKNOWN"
            title_name = os.path.basename(pkg_path)
            version = "1.00"
            category = "gd"

            if sfo_info:
                f.seek(sfo_info["offset"])
                parsed_sfo = parse_sfo(f.read(sfo_info["size"]))
                if parsed_sfo:
                    title_id = parsed_sfo.get("TITLE_ID", "UNKNOWN")
                    title_name = parsed_sfo.get("TITLE", title_name)
                    version = parsed_sfo.get("APP_VER", "1.00")
                    category = parsed_sfo.get("CATEGORY", category)

            if json_info:
                f.seek(json_info["offset"])
                try:
                    raw_json = f.read(json_info["size"]).decode('utf-8', errors='ignore').strip('\x00')
                    last_brace = raw_json.rfind('}')
                    if last_brace != -1:
                        raw_json = raw_json[:last_brace+1]
                    parsed_json = json.loads(raw_json)
                    title_id = parsed_json.get("titleId", parsed_json.get("title_id", title_id))
                    title_name = extract_ps5_title(parsed_json, title_name)
                    version = parsed_json.get("contentVersion", version)
                    if "category" in parsed_json:
                        category = parsed_json["category"]
                    elif parsed_json.get("applicationCategoryType") == 0:
                        category = "gd"
                except Exception as e:
                    logger.warning(f"param.json reading warning for {pkg_path}: {e}")

            if title_id == "UNKNOWN" or not (sfo_info or json_info):
                logger.info(f"PKG has no standard SFO/JSON entry. Attempting heuristic recovery for: {os.path.basename(pkg_path)}")
                h_tid, h_tname, h_plat, h_role, h_ver = guess_metadata_from_path(pkg_path, content_id)
                if h_tid != "UNKNOWN":
                    title_id = h_tid
                    if title_name == os.path.basename(pkg_path) and h_tname != os.path.basename(pkg_path):
                        title_name = h_tname
                    platform = h_plat
                    category = "gp" if h_role == "Patch" else ("ac" if h_role == "DLC" else "gd")
                    version = h_ver
                    logger.info(f"Heuristically resolved: {title_name} ({title_id}) as {platform} {h_role} v{version}")
                else:
                    return create_error_entry(pkg_path, file_size, f"No valid metadata found (entries: {entry_count})")

            if title_id.startswith("PPSA"):
                platform = "PS5"
            elif title_id.startswith("CUSA"):
                platform = "PS4"

            cat_lower = str(category).lower()
            if cat_lower in ("gd", "gdo"):
                role = "Game"
            elif cat_lower in ("gp", "gdp"):
                role = "Patch"
            elif cat_lower in ("ac", "gda"):
                role = "DLC"
            else:
                fl = (pkg_path + " " + content_id).lower()
                if any(k in fl for k in ["backport", "backpork", "patch", "update", "bp4", "bp5", "fullrus"]):
                    role = "Patch"
                elif any(k in fl for k in ["dlc", "bonus", "pre-order", "preorder"]):
                    role = "DLC"
                else:
                    role = "Game"

            path_hash = hashlib.md5(pkg_path.encode('utf-8')).hexdigest()
            unique_catalog_id = f"{title_id}_{path_hash[:6]}"

            icon_path, has_icon = "", False
            if icon_data:
                try:
                    f.seek(icon_data["offset"])
                    icon_path = os.path.join(ICONS_DIR, f"{title_id}_{path_hash}_icon.png")
                    with open(icon_path, "wb") as icon_file:
                        icon_file.write(f.read(icon_data["size"]))
                    has_icon = True
                except Exception:
                    pass

            logger.info(f"Successfully parsed {title_name} ({title_id}) as {platform} {role} v{version}")

            return {
                "catalog": {
                    "id": unique_catalog_id,
                    "title": title_name,
                    "titleId": title_id,
                    "version": version,
                    "size": file_size,
                    "sizeText": format_size(file_size),
                    "role": role,
                    "familyKey": title_id,
                    "platform": platform,
                    "format": "pkg",
                    "file": f"{unique_catalog_id}.pkg",
                    "originalFilename": os.path.basename(pkg_path),
                    "fullPath": pkg_path,
                    "hasIcon": has_icon,
                    "error": False
                },
                "local_pkg": pkg_path,
                "local_icon": icon_path
            }

    except Exception as e:
        msg = f"Parsing exception: {str(e)}"
        logger.error(f"Error parsing PKG {pkg_path}: {e}", exc_info=True)
        return create_error_entry(pkg_path, file_size if file_size else 0, msg)
