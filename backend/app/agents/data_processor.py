"""
SheetFlow AI - Data Processor Agent
Coding agent that generates and executes Pandas code for data cleaning.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from io import BytesIO
from dataclasses import dataclass, field

import pandas as pd
import numpy as np
import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of data processing."""
    sheets: Dict[str, pd.DataFrame]
    unified_df: Optional[pd.DataFrame] = None
    cleaning_log: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class DataProcessor:
    """
    Coding agent that processes messy Excel files using Pandas.
    
    Capabilities:
    - Multi-sheet loading and reasoning
    - Skip empty/header rows
    - Normalize column names
    - Handle missing values
    - Type inference and conversion
    - Cross-sheet joins based on AI analysis
    """
    
    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Initialize data processor.
        
        Args:
            gemini_api_key: Optional API key for AI-powered analysis
        """
        self.gemini_api_key = gemini_api_key
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            self.model = None
    
    def load_all_sheets(self, file_bytes: bytes) -> Dict[str, pd.DataFrame]:
        """
        Load all sheets from an Excel file.
        
        Args:
            file_bytes: Raw Excel file bytes
            
        Returns:
            Dict of sheet_name -> DataFrame
        """
        sheets = {}
        excel_file = pd.ExcelFile(BytesIO(file_bytes))
        
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                if not df.empty:
                    sheets[sheet_name] = df
                    logger.info(f"Loaded sheet '{sheet_name}': {df.shape}")
            except Exception as e:
                logger.warning(f"Failed to load sheet '{sheet_name}': {e}")
        
        return sheets
    
    def normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to snake_case.
        
        Changes:
        - Lowercase
        - Replace spaces/special chars with underscores
        - Remove duplicate underscores
        - Strip leading/trailing underscores
        """
        def clean_name(name: str) -> str:
            if not isinstance(name, str):
                name = str(name)
            # Lowercase and replace special chars
            name = name.lower()
            name = re.sub(r'[^a-z0-9]', '_', name)
            # Remove duplicate underscores
            name = re.sub(r'_+', '_', name)
            # Strip leading/trailing
            name = name.strip('_')
            return name or 'unnamed'
        
        df.columns = [clean_name(col) for col in df.columns]
        
        # Handle duplicate column names
        seen = {}
        new_cols = []
        for col in df.columns:
            if col in seen:
                seen[col] += 1
                new_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                new_cols.append(col)
        df.columns = new_cols
        
        return df
    
    def detect_header_row(self, df: pd.DataFrame) -> int:
        """
        Detect the actual header row in a messy Excel file.
        
        Looks for the first row that looks like column headers
        (mostly strings, not empty).
        
        Returns:
            Row index that should be the header (0-based)
        """
        for i in range(min(10, len(df))):  # Check first 10 rows
            row = df.iloc[i]
            
            # Skip mostly empty rows
            non_empty = row.dropna()
            if len(non_empty) < len(row) * 0.5:
                continue
            
            # Check if row looks like headers (mostly strings)
            string_count = sum(1 for v in row if isinstance(v, str) and v.strip())
            if string_count >= len(row) * 0.5:
                return i
        
        return 0  # Default to first row
    
    def skip_empty_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows that are completely or mostly empty."""
        # Calculate non-null percentage per row
        threshold = 0.3  # At least 30% of columns should have values
        mask = df.notna().sum(axis=1) >= (len(df.columns) * threshold)
        return df[mask].reset_index(drop=True)
    
    def handle_missing_values(
        self, 
        df: pd.DataFrame,
        strategy: str = "smart"
    ) -> pd.DataFrame:
        """
        Handle missing values with configurable strategy.
        
        Strategies:
        - 'drop': Drop rows with any missing values
        - 'fill_zero': Fill numeric with 0, strings with empty
        - 'fill_mean': Fill numeric with mean, strings with mode
        - 'smart': AI-guided filling based on column context
        """
        if strategy == "drop":
            return df.dropna()
        
        for col in df.columns:
            if df[col].isna().sum() == 0:
                continue
            
            dtype = df[col].dtype
            
            if pd.api.types.is_numeric_dtype(dtype):
                if strategy == "fill_zero":
                    df[col] = df[col].fillna(0)
                elif strategy in ("fill_mean", "smart"):
                    df[col] = df[col].fillna(df[col].mean())
            else:
                if strategy == "fill_zero":
                    df[col] = df[col].fillna("")
                elif strategy in ("fill_mean", "smart"):
                    mode = df[col].mode()
                    if len(mode) > 0:
                        df[col] = df[col].fillna(mode[0])
                    else:
                        df[col] = df[col].fillna("")
        
        return df
    
    def infer_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Infer and convert column types.
        
        Tries to convert string columns to:
        - Numeric (int/float)
        - Datetime
        - Boolean
        """
        for col in df.columns:
            if df[col].dtype != object:
                continue
            
            # Try numeric conversion
            try:
                numeric = pd.to_numeric(df[col], errors='coerce')
                if numeric.notna().sum() > len(df) * 0.5:
                    df[col] = numeric
                    continue
            except:
                pass
            
            # Try datetime conversion
            try:
                # Check for date-like patterns
                sample = df[col].dropna().head(5)
                if any(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', str(v)) for v in sample):
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    continue
            except:
                pass
            
            # Try boolean conversion
            try:
                lower = df[col].str.lower().str.strip()
                bool_map = {'true': True, 'false': False, 'yes': True, 'no': False, '1': True, '0': False}
                if lower.isin(list(bool_map.keys()) + [pd.NA, None]).all():
                    df[col] = lower.map(bool_map)
                    continue
            except:
                pass
        
        return df
    
    async def analyze_join_strategy(
        self,
        sheets: Dict[str, pd.DataFrame]
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to analyze sheets and suggest join strategy.
        
        Args:
            sheets: Dict of sheet_name -> DataFrame
            
        Returns:
            Join strategy dict or None if sheets should stay separate
        """
        if not self.model or len(sheets) < 2:
            return None
        
        # Build schema summary
        schema_info = {}
        for name, df in sheets.items():
            schema_info[name] = {
                "columns": list(df.columns),
                "row_count": len(df),
                "sample": df.head(2).to_dict()
            }
        
        prompt = f"""Analyze these Excel sheets and determine if/how they should be joined:

{schema_info}

Consider:
1. Are there common key columns (e.g., product_id, date, customer_id)?
2. What type of join makes sense (inner, left, full)?
3. Should any sheets remain separate?

Return a JSON object with:
{{
    "should_join": true/false,
    "joins": [
        {{"left": "sheet1", "right": "sheet2", "on": "column_name", "how": "left"}}
    ],
    "keep_separate": ["sheet_name"],
    "reasoning": "explanation"
}}

JSON response:"""
        
        try:
            response = await self.model.generate_content_async(prompt)
            result_text = response.text.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                import json
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"AI join analysis failed: {e}")
        
        return None
    
    def execute_joins(
        self,
        sheets: Dict[str, pd.DataFrame],
        join_strategy: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        Execute join strategy to create unified DataFrame.
        
        Args:
            sheets: Dict of sheet_name -> DataFrame
            join_strategy: Strategy from AI analysis
            
        Returns:
            Unified DataFrame
        """
        if not join_strategy.get("should_join") or not join_strategy.get("joins"):
            # Return first sheet or concatenation
            if len(sheets) == 1:
                return list(sheets.values())[0]
            return pd.concat(sheets.values(), ignore_index=True)
        
        result = None
        
        for join in join_strategy["joins"]:
            left_name = join["left"]
            right_name = join["right"]
            on_col = join["on"]
            how = join.get("how", "left")
            
            if left_name not in sheets or right_name not in sheets:
                continue
            
            left_df = result if result is not None else sheets[left_name]
            right_df = sheets[right_name]
            
            if on_col in left_df.columns and on_col in right_df.columns:
                result = pd.merge(left_df, right_df, on=on_col, how=how, suffixes=('', f'_{right_name}'))
                logger.info(f"Joined {left_name} + {right_name} on {on_col}")
        
        return result if result is not None else list(sheets.values())[0]
    
    async def process(
        self,
        file_bytes: bytes,
        clean_missing: str = "smart"
    ) -> ProcessingResult:
        """
        Full processing pipeline for an Excel file.
        
        Steps:
        1. Load all sheets
        2. Detect and fix header rows
        3. Normalize column names
        4. Skip empty rows
        5. Handle missing values
        6. Infer types
        7. Analyze and execute joins
        
        Args:
            file_bytes: Raw Excel file bytes
            clean_missing: Missing value strategy
            
        Returns:
            ProcessingResult with cleaned data
        """
        result = ProcessingResult(sheets={})
        
        # 1. Load all sheets
        raw_sheets = self.load_all_sheets(file_bytes)
        result.cleaning_log.append(f"Loaded {len(raw_sheets)} sheets")
        
        # 2-6. Process each sheet
        for name, df in raw_sheets.items():
            try:
                # Detect header row
                header_idx = self.detect_header_row(df)
                if header_idx > 0:
                    df.columns = df.iloc[header_idx]
                    df = df.iloc[header_idx + 1:].reset_index(drop=True)
                    result.cleaning_log.append(f"{name}: Moved header from row {header_idx}")
                
                # Normalize columns
                df = self.normalize_column_names(df)
                
                # Skip empty rows
                original_len = len(df)
                df = self.skip_empty_rows(df)
                if len(df) < original_len:
                    result.cleaning_log.append(f"{name}: Removed {original_len - len(df)} empty rows")
                
                # Handle missing values
                df = self.handle_missing_values(df, strategy=clean_missing)
                
                # Infer types
                df = self.infer_types(df)
                
                result.sheets[name] = df
                
            except Exception as e:
                result.errors.append(f"Error processing {name}: {e}")
                logger.error(f"Sheet processing error: {e}")
        
        # 7. Analyze and execute joins
        if len(result.sheets) > 1:
            join_strategy = await self.analyze_join_strategy(result.sheets)
            if join_strategy:
                result.unified_df = self.execute_joins(result.sheets, join_strategy)
                result.cleaning_log.append(f"Created unified view with {len(result.unified_df)} rows")
            else:
                # Just use the first sheet as primary
                result.unified_df = list(result.sheets.values())[0]
        elif result.sheets:
            result.unified_df = list(result.sheets.values())[0]
        
        return result
