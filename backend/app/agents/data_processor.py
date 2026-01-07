"""
SheetFlow AI - Agentic Data Processor
Tool-based reasoning system for intelligent data cleaning and processing.
"""
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from io import BytesIO
from dataclasses import dataclass, field

import pandas as pd
import numpy as np
import google.generativeai as genai

from app.agents.tools import DataTools

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of data processing with detailed reasoning."""
    sheets: Dict[str, pd.DataFrame]
    unified_df: Optional[pd.DataFrame] = None
    cleaning_log: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    reasoning: List[Dict[str, str]] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)


@dataclass
class StructureProbe:
    """Results from structural probing of a sheet."""
    sheet_name: str
    header_row: int
    header_confidence: float
    column_types: Dict[str, str]
    null_metrics: Dict[str, Dict]
    row_count: int
    issues: List[str] = field(default_factory=list)


class DataProcessor:
    """
    Agentic data processor that uses tools for intelligent processing.
    
    Multi-Phase Processing:
    1. Context Awareness - Fetch file context before processing
    2. Structural Probing - Use tools to understand data layout
    3. Quality Assessment - Check data quality before transformations
    4. Dynamic Transformation - Apply cleaning based on probe results
    5. Intelligent Joins - Test join quality before executing
    """
    
    def __init__(
        self, 
        gemini_api_key: Optional[str] = None,
        file_contexts: Optional[List[Dict[str, str]]] = None,
        global_description: Optional[str] = None
    ):
        """
        Initialize agentic data processor.
        
        Args:
            gemini_api_key: Optional API key for AI-powered analysis
            file_contexts: List of {file_name, file_context} from user
            global_description: User's overall dashboard purpose
        """
        self.gemini_api_key = gemini_api_key
        self.file_contexts = file_contexts or []
        self.global_description = global_description
        
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
    
    # =========================================================================
    # PHASE 1: STRUCTURAL PROBING (Tool-Based)
    # =========================================================================
    
    def probe_structure(
        self, 
        sheets: Dict[str, pd.DataFrame]
    ) -> Dict[str, StructureProbe]:
        """
        Use DataTools to probe the structure of each sheet.
        
        Replaces hardcoded detect_header_row and infer_types with tool-based discovery.
        """
        tools = DataTools(
            dataframes=sheets,
            file_contexts=self.file_contexts,
            global_description=self.global_description
        )
        
        probes = {}
        
        for sheet_name in sheets.keys():
            issues = []
            
            # Tool: detect_header_row
            header_result = tools.detect_header_row(sheet_name)
            header_row = 0
            header_confidence = 1.0
            
            if header_result.success:
                header_row = header_result.data.get("header_row", 0)
                header_confidence = header_result.data.get("confidence", 1.0)
                unnamed_cols = header_result.data.get("unnamed_columns", 0)
                
                if unnamed_cols > 0:
                    issues.append(f"Found {unnamed_cols} unnamed columns - may need header adjustment")
            
            # Tool: get_column_types
            types_result = tools.get_column_types(sheet_name)
            column_types = types_result.data if types_result.success else {}
            
            # Tool: calculate_null_metrics
            null_result = tools.calculate_null_metrics(sheet_name)
            null_metrics = {}
            if null_result.success:
                # Flag columns with high null rates
                for col, metrics in null_result.data.items():
                    if metrics.get("null_pct", 0) > 30:
                        issues.append(f"Column '{col}' has {metrics['null_pct']}% nulls")
                    null_metrics[col] = metrics
            
            probes[sheet_name] = StructureProbe(
                sheet_name=sheet_name,
                header_row=header_row,
                header_confidence=header_confidence,
                column_types=column_types,
                null_metrics=null_metrics,
                row_count=len(sheets[sheet_name]),
                issues=issues
            )
            
            logger.info(f"Probed {sheet_name}: header_row={header_row}, types={len(column_types)}, issues={len(issues)}")
        
        return probes
    
    # =========================================================================
    # PHASE 2: QUALITY ASSESSMENT
    # =========================================================================
    
    def assess_quality(
        self, 
        sheets: Dict[str, pd.DataFrame],
        probes: Dict[str, StructureProbe]
    ) -> Dict[str, List[str]]:
        """
        Assess data quality and identify issues before transformation.
        
        Returns dict of sheet_name -> list of quality issues
        """
        tools = DataTools(
            dataframes=sheets,
            file_contexts=self.file_contexts
        )
        
        quality_issues = {}
        
        for sheet_name, probe in probes.items():
            issues = list(probe.issues)  # Start with probe issues
            
            # Check for date columns that need format validation
            for col, col_type in probe.column_types.items():
                if col_type in ("DateString", "DateTime"):
                    format_result = tools.validate_date_formats(sheet_name, col)
                    if format_result.success:
                        consistency = format_result.data.get("consistency_pct", 100)
                        if consistency < 90:
                            issues.append(
                                f"Column '{col}' has inconsistent date formats ({consistency}% consistent)"
                            )
            
            # Check for currency columns
            currency_result = tools.identify_currency_symbols(sheet_name)
            if currency_result.success and currency_result.data:
                for col, currency in currency_result.data.items():
                    issues.append(f"Column '{col}' contains {currency} values - will need parsing")
            
            quality_issues[sheet_name] = issues
        
        return quality_issues
    
    # =========================================================================
    # PHASE 3: INTELLIGENT JOINS (Tool-Based)
    # =========================================================================
    
    async def analyze_joins_with_tools(
        self, 
        sheets: Dict[str, pd.DataFrame],
        result: ProcessingResult
    ) -> Optional[Dict[str, Any]]:
        """
        Use DataTools to find and validate join keys between sheets.
        
        Much more reliable than AI-only analysis because it actually tests the data.
        """
        if len(sheets) < 2:
            return None
        
        tools = DataTools(
            dataframes=sheets,
            file_contexts=self.file_contexts,
            global_description=self.global_description
        )
        
        sheet_names = list(sheets.keys())
        best_joins = []
        
        for i, sheet1 in enumerate(sheet_names):
            for sheet2 in sheet_names[i+1:]:
                # Tool: suggest_join_keys
                suggestions = tools.suggest_join_keys(sheet1, sheet2)
                result.tools_used.append(f"suggest_join_keys({sheet1}, {sheet2})")
                
                if not suggestions.success or not suggestions.data:
                    result.reasoning.append({
                        "action": "skip_join",
                        "sheets": f"{sheet1} + {sheet2}",
                        "reason": "No common columns found by tool"
                    })
                    continue
                
                # Test each suggestion
                for suggestion in suggestions.data:
                    col1, col2 = suggestion["col1"], suggestion["col2"]
                    overlap_pct = suggestion["overlap_pct"]
                    
                    if overlap_pct < 20:
                        continue
                    
                    # Tool: test_join_quality
                    quality = tools.test_join_quality(sheet1, sheet2, col1, col2)
                    result.tools_used.append(f"test_join_quality({sheet1}, {sheet2}, {col1}, {col2})")
                    
                    if quality.success:
                        match_pct = min(
                            quality.data.get("match_pct_sheet1", 0),
                            quality.data.get("match_pct_sheet2", 0)
                        )
                        
                        if match_pct >= 50:
                            best_joins.append({
                                "left": sheet1,
                                "right": sheet2,
                                "left_col": col1,
                                "right_col": col2,
                                "match_pct": match_pct,
                                "quality_data": quality.data
                            })
                            
                            result.reasoning.append({
                                "action": "join_found",
                                "sheets": f"{sheet1} + {sheet2}",
                                "key": f"{col1} = {col2}",
                                "reason": f"Match quality: {match_pct}% ({quality.data.get('recommendation', '')})"
                            })
                            
                            result.cleaning_log.append(
                                f"✓ Found join: {sheet1}.{col1} ↔ {sheet2}.{col2} ({match_pct}% match)"
                            )
                            break  # Use first good match
                        
                        elif match_pct >= 30:
                            # Low quality warning
                            result.cleaning_log.append(
                                f"⚠️ Low join quality: {sheet1}.{col1} ↔ {sheet2}.{col2} ({match_pct}% match)"
                            )
        
        if best_joins:
            # Sort by match quality
            best_joins.sort(key=lambda x: x["match_pct"], reverse=True)
            return {"should_join": True, "joins": best_joins}
        
        return None
    
    # =========================================================================
    # TRANSFORMATION METHODS
    # =========================================================================
    
    def normalize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to snake_case."""
        def clean_name(name: str) -> str:
            if not isinstance(name, str):
                name = str(name)
            name = name.lower()
            name = re.sub(r'[^a-z0-9]', '_', name)
            name = re.sub(r'_+', '_', name)
            name = name.strip('_')
            return name or 'unnamed'
        
        df.columns = [clean_name(col) for col in df.columns]
        
        # Handle duplicates
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
    
    def apply_header_correction(
        self, 
        df: pd.DataFrame, 
        probe: StructureProbe,
        result: ProcessingResult
    ) -> pd.DataFrame:
        """Apply header row correction based on probe results."""
        if probe.header_row > 0:
            # Move header from detected row
            df.columns = df.iloc[probe.header_row]
            df = df.iloc[probe.header_row + 1:].reset_index(drop=True)
            
            result.cleaning_log.append(
                f"{probe.sheet_name}: Skipped first {probe.header_row} rows (metadata headers detected)"
            )
            result.reasoning.append({
                "action": "header_correction",
                "sheet": probe.sheet_name,
                "reason": f"Tool detected header at row {probe.header_row} with {probe.header_confidence:.0%} confidence"
            })
        
        return df
    
    def skip_empty_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows that are mostly empty."""
        threshold = 0.3
        mask = df.notna().sum(axis=1) >= (len(df.columns) * threshold)
        return df[mask].reset_index(drop=True)
    
    def handle_missing_values(
        self, 
        df: pd.DataFrame,
        null_metrics: Dict[str, Dict],
        strategy: str = "smart"
    ) -> pd.DataFrame:
        """Handle missing values with awareness of null metrics from probe."""
        for col in df.columns:
            if df[col].isna().sum() == 0:
                continue
            
            metrics = null_metrics.get(col, {})
            null_pct = metrics.get("null_pct", 0)
            
            # If too many nulls, don't try to fill
            if null_pct > 50:
                continue
            
            dtype = df[col].dtype
            
            if pd.api.types.is_numeric_dtype(dtype):
                if strategy == "smart" and null_pct < 20:
                    df[col] = df[col].fillna(df[col].mean())
                else:
                    df[col] = df[col].fillna(0)
            else:
                mode = df[col].mode()
                if len(mode) > 0 and null_pct < 20:
                    df[col] = df[col].fillna(mode[0])
                else:
                    df[col] = df[col].fillna("")
        
        return df
    
    def infer_types_from_probe(
        self, 
        df: pd.DataFrame, 
        column_types: Dict[str, str]
    ) -> pd.DataFrame:
        """Apply type conversions based on probe results."""
        for col, detected_type in column_types.items():
            if col not in df.columns:
                continue
            
            try:
                if detected_type == "Integer":
                    df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
                elif detected_type == "Float":
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                elif detected_type in ("DateTime", "DateString"):
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                elif detected_type == "Currency":
                    # Remove currency symbols and convert
                    df[col] = df[col].astype(str).str.replace(r'[₪$€£,]', '', regex=True)
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                logger.warning(f"Type conversion failed for {col}: {e}")
        
        return df
    
    def execute_joins(
        self,
        sheets: Dict[str, pd.DataFrame],
        join_strategy: Dict[str, Any],
        result: ProcessingResult
    ) -> pd.DataFrame:
        """Execute validated joins to create unified DataFrame."""
        if not join_strategy.get("should_join") or not join_strategy.get("joins"):
            if len(sheets) == 1:
                return list(sheets.values())[0]
            return pd.concat(sheets.values(), ignore_index=True)
        
        unified = None
        
        for join in join_strategy["joins"]:
            left_name = join["left"]
            right_name = join["right"]
            left_col = join["left_col"]
            right_col = join["right_col"]
            
            if left_name not in sheets or right_name not in sheets:
                continue
            
            left_df = unified if unified is not None else sheets[left_name]
            right_df = sheets[right_name]
            
            # Handle column name differences
            if left_col != right_col:
                right_df = right_df.rename(columns={right_col: left_col})
            
            if left_col in left_df.columns and left_col in right_df.columns:
                try:
                    unified = pd.merge(
                        left_df, right_df, 
                        on=left_col, 
                        how="left", 
                        suffixes=('', f'_{right_name}')
                    )
                    result.cleaning_log.append(
                        f"✓ Joined {left_name} + {right_name} on '{left_col}' → {len(unified)} rows"
                    )
                except Exception as e:
                    result.errors.append(f"Join failed: {e}")
                    result.cleaning_log.append(f"✗ Join failed: {left_name} + {right_name}")
        
        return unified if unified is not None else list(sheets.values())[0]
    
    # =========================================================================
    # MAIN PROCESSING PIPELINE
    # =========================================================================
    
    async def process(
        self,
        file_bytes: bytes,
        clean_missing: str = "smart"
    ) -> ProcessingResult:
        """
        Full agentic processing pipeline.
        
        Phases:
        1. Load sheets
        2. Structural probing (tool-based)
        3. Quality assessment
        4. Apply transformations based on probe results
        5. Intelligent joins with quality testing
        """
        result = ProcessingResult(sheets={})
        
        # === Phase 1: Load all sheets ===
        raw_sheets = self.load_all_sheets(file_bytes)
        result.cleaning_log.append(f"📂 Loaded {len(raw_sheets)} sheets")
        
        if not raw_sheets:
            result.errors.append("No data could be loaded from file")
            return result
        
        # === Phase 2: Structural Probing ===
        result.cleaning_log.append("🔍 Probing data structure...")
        probes = self.probe_structure(raw_sheets)
        result.tools_used.extend([
            "detect_header_row", "get_column_types", "calculate_null_metrics"
        ])
        
        # === Phase 3: Quality Assessment ===
        quality_issues = self.assess_quality(raw_sheets, probes)
        for sheet_name, issues in quality_issues.items():
            if issues:
                result.cleaning_log.append(f"⚠️ {sheet_name}: {len(issues)} quality issues detected")
        
        # === Phase 4: Apply Transformations ===
        result.cleaning_log.append("🧹 Applying transformations...")
        
        for name, df in raw_sheets.items():
            try:
                probe = probes.get(name)
                if not probe:
                    continue
                
                # Apply header correction from probe
                df = self.apply_header_correction(df, probe, result)
                
                # Normalize columns
                df = self.normalize_column_names(df)
                
                # Skip empty rows
                original_len = len(df)
                df = self.skip_empty_rows(df)
                if len(df) < original_len:
                    removed = original_len - len(df)
                    result.cleaning_log.append(f"{name}: Removed {removed} empty rows")
                
                # Handle missing values with probe awareness
                df = self.handle_missing_values(df, probe.null_metrics, strategy=clean_missing)
                
                # Apply type conversions from probe
                df = self.infer_types_from_probe(df, probe.column_types)
                
                result.sheets[name] = df
                
            except Exception as e:
                result.errors.append(f"Error processing {name}: {e}")
                logger.error(f"Processing error: {e}")
        
        # === Phase 5: Intelligent Joins ===
        if len(result.sheets) > 1:
            result.cleaning_log.append("🔗 Analyzing join possibilities...")
            join_strategy = await self.analyze_joins_with_tools(result.sheets, result)
            
            if join_strategy:
                result.unified_df = self.execute_joins(result.sheets, join_strategy, result)
                result.cleaning_log.append(
                    f"✅ Created unified view: {len(result.unified_df)} rows"
                )
            else:
                result.unified_df = list(result.sheets.values())[0]
                result.cleaning_log.append("ℹ️ No joins applied - using primary sheet")
        elif result.sheets:
            result.unified_df = list(result.sheets.values())[0]
        
        # Summary
        result.cleaning_log.append(f"🔧 Used {len(result.tools_used)} tool calls")
        
        return result
