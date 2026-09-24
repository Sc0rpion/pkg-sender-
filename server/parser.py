"""
Low-level parser module for extracting metadata from PlayStation PKG containers.
"""
import os
import struct
import json
import hashlib
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
    if len(sfo_bytes) < 20 or sfo_bytes[:4] != b'\x00PSF': return None
    try:
        key_table_offset, data_table_offset, entry_count = struct.unpack_from("<III", sfo_bytes, 0x08)
        info = {}
        for i in range(entry_count):
            key_off, fmt, length, max_len, data_off = struct.unpack_from("<HHIII", sfo_bytes, 0x14 + i * 16)
            key_end = sfo_bytes.find(b'\x00', key_table_offset + key_off)
            if key_end == -1: continue
            key = sfo_bytes[key_table_offset + key_off : key_end].decode('utf-8')
            data_start = data_table_offset + data_off
            
            if fmt == 0x0204:
                val = sfo_bytes[data_start : data_start + length].split(b'\x00')[0].decode('utf-8', errors='ignore')
            elif fmt == 0x0404:
                val = struct.unpack_from("<I", sfo_bytes, data_start)[0]
            else: val = None
            if val is not None: info[key] = val
        return info
    except Exception as e:
        logger.error(f"SFO parsing error: {str(e)}")
        return None

def extract_ps5_title(parsed_json, original_name):
    localized = parsed_json.get("localizedParameters", {})
    if localized:
        default_lang = localized.get("defaultLanguage")
        if default_lang and default_lang in localized:
            title = localized[default_lang].get("titleName")
            if title: return title
            
        for fallback in ["en-US", "en-GB"]:
            if fallback in localized and localized[fallback].get("titleName"):
                return localized[fallback].get("titleName")
                
        for lang_data in localized.values():
            if isinstance(lang_data, dict) and lang_data.get("titleName"):
                return lang_data.get("titleName")
                
    return parsed_json.get("titleName", original_name)

def extract_pkg_meta(pkg_path):
    try:
        file_size = os.path.getsize(pkg_path)
        if file_size < 2000:
            msg = f"File too small ({file_size} bytes)"
            return create_error_entry(pkg_path, file_size, msg)

        with open(pkg_path, 'rb') as f:
            magic = f.read(4)
            cnt_offset = 0
            platform = "PS4"
            
            if magic == b'\x7FFIH':
                platform = "PS5"
                f.seek(0x58)
                ptr_data = f.read(8)
                if len(ptr_data) < 8: return create_error_entry(pkg_path, file_size, "Failed to read FIH")
                cnt_offset = struct.unpack("<Q", ptr_data)[0]
            elif magic == b'\x7FCNT':
                platform = "PS4"
                cnt_offset = 0
            else:
                return create_error_entry(pkg_path, file_size, f"Unknown magic [{magic.hex()}]")

            if cnt_offset >= file_size or cnt_offset < 0:
                return create_error_entry(pkg_path, file_size, f"Corrupted pointer: {cnt_offset}")

            f.seek(cnt_offset + 0x10)
            header_data = f.read(12)
            if len(header_data) < 12: return create_error_entry(pkg_path, file_size, "EOF in CNT header")

            entry_count = struct.unpack(">I", header_data[0:4])[0]
            entry_table_offset = cnt_offset + struct.unpack(">I", header_data[8:12])[0]

            if entry_count == 0 or entry_count > 10000:
                return create_error_entry(pkg_path, file_size, f"Suspicious entries: {entry_count}")
            if entry_table_offset >= file_size:
                return create_error_entry(pkg_path, file_size, "Entry table outside file")

            table_size_bytes = entry_count * 32
            f.seek(entry_table_offset)
            entry_table = f.read(table_size_bytes)
            
            sfo_info = json_info = icon_data = None
            for i in range(entry_count):
                entry = entry_table[i*32 : (i+1)*32]
                e_id, _, _, _, e_off, e_size, _ = struct.unpack(">IIIIIIQ", entry)
                if cnt_offset + e_off + e_size > file_size: continue
                if e_id == 0x1000: sfo_info = {"offset": cnt_offset + e_off, "size": e_size}
                elif e_id == 0x2000: json_info = {"offset": cnt_offset + e_off, "size": e_size}
                elif e_id == 0x1200: icon_data = {"offset": cnt_offset + e_off, "size": e_size}

            if not (sfo_info or json_info):
                return create_error_entry(pkg_path, file_size, "No valid metadata found")

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
                    
                    # ИЗВЛЕЧЕНИЕ ВЕРСИИ PS5 (БЕЗ masterVersion)
                    version = parsed_json.get("contentVersion", version)
                    
                    if "category" in parsed_json:
                        category = parsed_json["category"]
                    elif parsed_json.get("applicationCategoryType") == 0:
                        category = "gd"
                except Exception as e:
                    logger.warning(f"Skipped param.json parsing for {title_name}: {e}")

            cat_lower = category.lower()
            if cat_lower in ("gd", "gdo", "unknown"): 
                role = "Game"
            elif cat_lower in ("gp", "gdp"): 
                role = "Patch"
            elif cat_lower in ("ac", "gda"): 
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
                except: pass

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
        logger.error(msg)
        return create_error_entry(pkg_path, os.path.getsize(pkg_path), msg)