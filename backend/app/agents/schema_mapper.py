"""
SheetFlow AI - Schema Mapper
Detects schema drift between Excel versions and auto-remaps columns.
"""
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import pandas as pd
import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class ColumnDrift:
    """Represents a single column change."""
    column_name: str
    change_type: str  # 'added', 'removed', 'renamed', 'type_changed'
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    confidence: float = 1.0


@dataclass
class DriftReport:
    """Complete drift report for a sheet."""
    sheet_name: str
    has_drift: bool = False
    added_columns: List[str] = field(default_factory=list)
    removed_columns: List[str] = field(default_factory=list)
    renamed_columns: Dict[str, str] = field(default_factory=dict)  # old -> new
    type_changes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # col -> {old, new}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sheet_name": self.sheet_name,
            "added_columns": self.added_columns,
            "removed_columns": self.removed_columns,
            "renamed_columns": self.renamed_columns,
            "type_changes": self.type_changes,
        }


class SchemaMapper:
    """
    Detects and handles schema drift between Excel file versions.
    
    Uses a combination of:
    1. Exact matching for unchanged columns
    2. Fuzzy string matching for likely renames
    3. Gemini AI for complex semantic matching
    """
    
    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Initialize schema mapper.
        
        Args:
            gemini_api_key: Optional API key for AI-powered matching
        """
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        else:
            self.model = None
    
    def extract_schema(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Extract column schema from DataFrame.
        
        Args:
            df: Pandas DataFrame
            
        Returns:
            Dict of column_name -> inferred_type
        """
        schema = {}
        for col in df.columns:
            dtype = df[col].dtype
            if pd.api.types.is_numeric_dtype(dtype):
                if pd.api.types.is_integer_dtype(dtype):
                    schema[col] = "integer"
                else:
                    schema[col] = "float"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                schema[col] = "datetime"
            elif pd.api.types.is_bool_dtype(dtype):
                schema[col] = "boolean"
            else:
                schema[col] = "string"
        return schema
    
    def detect_drift(
        self, 
        old_schema: Dict[str, Dict[str, str]], 
        new_schema: Dict[str, Dict[str, str]]
    ) -> List[DriftReport]:
        """
        Detect schema drift between old and new schemas.
        
        Args:
            old_schema: Previous schema {sheet_name: {column: type}}
            new_schema: Current schema {sheet_name: {column: type}}
            
        Returns:
            List of DriftReport for each sheet
        """
        reports = []
        
        all_sheets = set(old_schema.keys()) | set(new_schema.keys())
        
        for sheet_name in all_sheets:
            old_cols = old_schema.get(sheet_name, {})
            new_cols = new_schema.get(sheet_name, {})
            
            report = DriftReport(sheet_name=sheet_name)
            
            old_set = set(old_cols.keys())
            new_set = set(new_cols.keys())
            
            # Find added and removed
            added = new_set - old_set
            removed = old_set - new_set
            
            # Try to match removed -> added (potential renames)
            renamed = self._find_renames(
                list(removed), 
                list(added), 
                old_cols, 
                new_cols
            )
            
            # Update sets based on renames
            for old_name, new_name in renamed.items():
                removed.discard(old_name)
                added.discard(new_name)
            
            report.added_columns = list(added)
            report.removed_columns = list(removed)
            report.renamed_columns = renamed
            
            # Check for type changes in matching columns
            matching = old_set & new_set
            for col in matching:
                old_type = old_cols[col]
                new_type = new_cols[col]
                if old_type != new_type:
                    report.type_changes[col] = {"old": old_type, "new": new_type}
            
            report.has_drift = bool(
                report.added_columns or 
                report.removed_columns or 
                report.renamed_columns or 
                report.type_changes
            )
            
            reports.append(report)
        
        return reports
    
    def _find_renames(
        self,
        removed: List[str],
        added: List[str],
        old_types: Dict[str, str],
        new_types: Dict[str, str],
        threshold: float = 0.6
    ) -> Dict[str, str]:
        """
        Find likely column renames using fuzzy matching.
        
        Args:
            removed: List of removed column names
            added: List of added column names
            old_types: Old column types
            new_types: New column types
            threshold: Minimum similarity score (0-1)
            
        Returns:
            Dict of old_name -> new_name for likely renames
        """
        renamed = {}
        used_new = set()
        
        for old_name in removed:
            best_match = None
            best_score = threshold
            
            for new_name in added:
                if new_name in used_new:
                    continue
                
                # Calculate name similarity
                name_score = SequenceMatcher(
                    None, 
                    old_name.lower().replace("_", " "),
                    new_name.lower().replace("_", " ")
                ).ratio()
                
                # Boost score if types match
                type_match = old_types.get(old_name) == new_types.get(new_name)
                score = name_score * 0.7 + (0.3 if type_match else 0)
                
                if score > best_score:
                    best_score = score
                    best_match = new_name
            
            if best_match:
                renamed[old_name] = best_match
                used_new.add(best_match)
        
        return renamed
    
    async def ai_remap(
        self,
        removed_columns: List[str],
        added_columns: List[str],
        sample_data: Dict[str, List[Any]]
    ) -> Dict[str, str]:
        """
        Use Gemini to intelligently map renamed columns based on context.
        
        Args:
            removed_columns: Columns that disappeared
            added_columns: New columns that appeared
            sample_data: Sample values from both old and new columns
            
        Returns:
            Dict of old_name -> new_name mappings
        """
        if not self.model or not removed_columns or not added_columns:
            return {}
        
        prompt = f"""Analyze these Excel column changes and identify which removed columns were likely renamed to which new columns.

REMOVED COLUMNS: {removed_columns}
NEW COLUMNS: {added_columns}

Sample data context:
{sample_data}

Return ONLY a JSON object mapping old column names to their likely new names.
Example: {{"old_price": "unit_cost", "qty": "quantity"}}
If no clear mappings exist, return an empty object: {{}}

JSON response:"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            result_text = response.text.strip()
            
            # Parse JSON response
            if result_text.startswith("{"):
                import json
                return json.loads(result_text)
        except Exception as e:
            logger.warning(f"AI remap failed: {e}")
        
        return {}
    
    def apply_remap(
        self, 
        df: pd.DataFrame, 
        drift: DriftReport
    ) -> pd.DataFrame:
        """
        Apply column remapping to a DataFrame based on drift report.
        
        Args:
            df: DataFrame to remap
            drift: Drift report with renamed_columns
            
        Returns:
            DataFrame with remapped columns
        """
        if not drift.renamed_columns:
            return df
        
        # Reverse the mapping (new -> old) for rename
        # We want to restore old names for consistency with dashboard config
        reverse_map = {v: k for k, v in drift.renamed_columns.items()}
        
        return df.rename(columns=reverse_map)
