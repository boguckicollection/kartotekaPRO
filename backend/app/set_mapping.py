"""
Set symbol (ptcgoCode) to Shoper category_id mapping.

Maps set symbols like TWM, PAL, OBF to their corresponding Shoper category IDs.
This allows automatic category assignment when scanning cards.
"""

from __future__ import annotations

import json
import os
from typing import Optional


class SetMapper:
    """Maps set symbols (ptcgoCode) to Shoper category IDs."""
    
    _instance = None
    _ptcgo_to_category: dict[str, str] = {}
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._load_mappings()
            self.__class__._initialized = True
    
    def _load_mappings(self):
        """Load mapping from tcg_sets.json and ids_dump.json."""
        try:
            # Find tcg_sets.json
            possible_paths = [
                "/app/tcg_sets.json",
                "tcg_sets.json",
                os.path.join(os.path.dirname(__file__), "../../tcg_sets.json"),
            ]
            
            tcg_sets_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    tcg_sets_path = p
                    break
            
            if not tcg_sets_path:
                print(f"ERROR: tcg_sets.json not found. Checked: {possible_paths}")
                return
            
            # Find ids_dump.json
            ids_dump_paths = [
                "/app/ids_dump.json",
                "ids_dump.json",
                os.path.join(os.path.dirname(__file__), "../../ids_dump.json"),
            ]
            
            ids_dump_path = None
            for p in ids_dump_paths:
                if os.path.exists(p):
                    ids_dump_path = p
                    break
            
            if not ids_dump_path:
                print(f"ERROR: ids_dump.json not found. Checked: {ids_dump_paths}")
                return
            
            # Load tcg_sets.json
            with open(tcg_sets_path, 'r', encoding='utf-8') as f:
                tcg_data = json.load(f)
            
            # Build ptcgoCode -> set name mapping
            ptcgo_to_name: dict[str, str] = {}
            for group_sets in tcg_data.values():
                for s in group_sets:
                    code = s.get('ptcgoCode')
                    name = s.get('name')
                    if code and name:
                        # Use first occurrence (avoid duplicates)
                        if code not in ptcgo_to_name:
                            ptcgo_to_name[code] = name
            
            # Load ids_dump.json
            with open(ids_dump_path, 'r', encoding='utf-8') as f:
                shoper_data = json.load(f)
            
            # Build set name -> category_id mapping from Shoper
            name_to_category: dict[str, str] = {}
            for cat in shoper_data.get('categories', []):
                cat_id = cat.get('category_id')
                translations = cat.get('translations', {}).get('pl_PL', {})
                cat_name = translations.get('name', '')
                if cat_id and cat_name:
                    name_to_category[cat_name] = cat_id
            
            # Combine: ptcgoCode -> set name -> category_id
            for code, name in ptcgo_to_name.items():
                if name in name_to_category:
                    self.__class__._ptcgo_to_category[code] = name_to_category[name]
            
            print(f"INFO: Loaded {len(self._ptcgo_to_category)} set symbol mappings")
            
        except Exception as e:
            print(f"ERROR: Failed to load set mappings: {e}")
    
    def get_category_id(self, set_symbol: str) -> Optional[str]:
        """
        Get Shoper category_id for a given set symbol (ptcgoCode).
        
        Args:
            set_symbol: Set symbol like "TWM", "PAL", "OBF"
        
        Returns:
            Category ID as string, or None if not found
        """
        if not set_symbol:
            return None
        
        # Normalize to uppercase
        normalized = str(set_symbol).upper().strip()
        return self._ptcgo_to_category.get(normalized)
    
    def get_all_mappings(self) -> dict[str, str]:
        """Get all available mappings (for debugging/testing)."""
        return self._ptcgo_to_category.copy()


# Singleton instance
_mapper = SetMapper()


def get_category_id_for_set_symbol(set_symbol: str) -> Optional[str]:
    """
    Get Shoper category_id for a given set symbol.
    
    Usage:
        category_id = get_category_id_for_set_symbol("TWM")  # Returns "49"
    """
    return _mapper.get_category_id(set_symbol)


def get_all_set_mappings() -> dict[str, str]:
    """Get all available set symbol -> category_id mappings."""
    return _mapper.get_all_mappings()
