"""
SheetFlow AI - AI Agent Service
LangGraph workflow for data processing with Gemini.
"""
import logging
from typing import Dict, List, Optional, Any, TypedDict
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from langgraph.graph import StateGraph, END
import google.generativeai as genai

from app.agents.data_processor import DataProcessor, ProcessingResult
from app.agents.schema_mapper import SchemaMapper, DriftReport
from app.agents.tools import DataTools

logger = logging.getLogger(__name__)


def make_serializable(obj: Any) -> Any:
    """Convert pandas/numpy types to JSON-serializable Python types."""
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(item) for item in obj]
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, (pd.NaT.__class__, type(pd.NaT))):
        return None
    elif pd.isna(obj):
        return None
    elif hasattr(obj, 'item'):  # numpy types
        return obj.item()
    return obj


class AgentState(TypedDict, total=False):
    """State passed through the LangGraph workflow."""
    # Input - supports both single file and multi-file modes
    file_bytes: bytes  # Single file mode (backwards compatible)
    files_data: List[Dict[str, Any]]  # Multi-file mode: [{file_id, file_name, file_bytes, file_context}]
    global_description: Optional[str]  # User context for the entire dashboard
    previous_schema: Dict[str, Dict[str, str]]
    accept_schema_drift: bool
    
    # Processing state
    sheets: Dict[str, Any]  # sheet_name -> DataFrame (as dict for serialization)
    unified_data: Optional[Dict[str, Any]]
    current_schema: Dict[str, Dict[str, str]]
    
    # Drift detection
    drift_reports: List[Dict[str, Any]]
    schema_drift_detected: bool
    
    # Output
    chart_suggestions: List[Dict[str, Any]]
    chart_data: Dict[str, Any]
    
    # Metadata
    messages: List[str]
    errors: List[str]
    
    # Internal (for passing data between nodes)
    _data_summary: Dict[str, Any]
    _file_contexts: List[Dict[str, str]]  # [{file_name, file_context}]
    _exploration_insights: Dict[str, Any]  # Tool-based exploration findings
    _tools_called: List[str]  # Track which tools were called


@dataclass  
class ProcessingOutput:
    """Final output from the AI agent."""
    sheet_names: List[str]
    new_schema: Dict[str, Dict[str, str]]
    schema_drift_detected: bool
    schema_drift_info: Optional[List[Dict[str, Any]]]
    chart_data: Dict[str, Any]
    suggested_charts: List[Dict[str, Any]]
    message: str


class DataProcessingAgent:
    """
    LangGraph-based AI agent for Excel data processing.
    
    Workflow:
    START -> load_sheets -> detect_schema_drift -> clean_data 
          -> analyze_data -> generate_charts -> END
    """
    
    def __init__(self, gemini_api_key: str):
        """
        Initialize the agent.
        
        Args:
            gemini_api_key: Google Gemini API key
        """
        self.gemini_api_key = gemini_api_key
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Initialize sub-agents
        self.data_processor = DataProcessor(gemini_api_key)
        self.schema_mapper = SchemaMapper(gemini_api_key)
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with exploration step."""
        workflow = StateGraph(AgentState)
        
        # Add nodes - including new explore_data node for AI reasoning
        workflow.add_node("load_sheets", self._load_sheets)
        workflow.add_node("explore_data", self._explore_data)  # NEW: AI exploration
        workflow.add_node("detect_schema_drift", self._detect_schema_drift)
        workflow.add_node("clean_data", self._clean_data)
        workflow.add_node("analyze_data", self._analyze_data)
        workflow.add_node("generate_charts", self._generate_charts)
        
        # Add edges - exploration happens after loading, before drift detection
        workflow.set_entry_point("load_sheets")
        workflow.add_edge("load_sheets", "explore_data")
        workflow.add_edge("explore_data", "detect_schema_drift")
        workflow.add_edge("detect_schema_drift", "clean_data")
        workflow.add_edge("clean_data", "analyze_data")
        workflow.add_edge("analyze_data", "generate_charts")
        workflow.add_edge("generate_charts", END)
        
        return workflow.compile()
    
    async def _load_sheets(self, state: AgentState) -> AgentState:
        """Load all sheets from Excel file."""
        try:
            sheets = self.data_processor.load_all_sheets(state["file_bytes"])
            
            # Convert to serializable format
            sheets_dict = {}
            for name, df in sheets.items():
                sheets_dict[name] = make_serializable(df.to_dict(orient='records'))
            
            state["sheets"] = sheets_dict
            state["messages"].append(f"Loaded {len(sheets)} sheets")
            
        except Exception as e:
            state["errors"].append(f"Load error: {str(e)}")
            logger.error(f"Sheet loading failed: {e}")
        
        return state
    
    async def _explore_data(self, state: AgentState) -> AgentState:
        """
        AI Reasoning Loop: Explore data using tools before generating charts.
        
        This step uses DataTools to understand:
        - Data structure and column types
        - Data quality (nulls, outliers)
        - Relationships between sheets (potential joins)
        """
        try:
            if not state.get("sheets"):
                return state
            
            # Convert sheets to DataFrames for tools
            dataframes = {}
            for name, records in state["sheets"].items():
                if records:
                    dataframes[name] = pd.DataFrame(records)
            
            if not dataframes:
                return state
            
            # Initialize tools with the data
            tools = DataTools(
                dataframes=dataframes,
                file_contexts=state.get("_file_contexts", []),
                global_description=state.get("global_description")
            )
            
            insights = {
                "files_overview": [],
                "column_types": {},
                "null_metrics": {},
                "join_suggestions": [],
                "time_series_columns": [],
                "data_quality_issues": []
            }
            tools_called = []
            
            # ===== ITERATION 0: Structural Exploration =====
            logger.info("AI Exploration - Iteration 0: Structural analysis")
            
            # List all files/sheets
            files_result = tools.list_dashboard_files()
            if files_result.success:
                insights["files_overview"] = files_result.data
                tools_called.append("list_dashboard_files")
            
            # Get column types for each sheet
            for sheet_name in dataframes.keys():
                types_result = tools.get_column_types(sheet_name)
                if types_result.success:
                    insights["column_types"][sheet_name] = types_result.data
                    tools_called.append(f"get_column_types({sheet_name})")
            
            # ===== ITERATION 1: Quality & Relationship Analysis =====
            logger.info("AI Exploration - Iteration 1: Quality and relationships")
            
            # Calculate null metrics for each sheet
            for sheet_name in dataframes.keys():
                null_result = tools.calculate_null_metrics(sheet_name)
                if null_result.success:
                    # Only keep columns with significant nulls
                    high_null_cols = {
                        col: metrics for col, metrics in null_result.data.items()
                        if metrics["null_pct"] > 5
                    }
                    if high_null_cols:
                        insights["null_metrics"][sheet_name] = high_null_cols
                        insights["data_quality_issues"].append(
                            f"{sheet_name}: {len(high_null_cols)} columns have >5% nulls"
                        )
                    tools_called.append(f"calculate_null_metrics({sheet_name})")
            
            # Find time series columns
            for sheet_name in dataframes.keys():
                ts_result = tools.identify_time_series(sheet_name)
                if ts_result.success and ts_result.data:
                    insights["time_series_columns"].extend([
                        {"sheet": sheet_name, **col} for col in ts_result.data
                    ])
                    tools_called.append(f"identify_time_series({sheet_name})")
            
            # If multiple sheets, find join possibilities
            sheet_names = list(dataframes.keys())
            if len(sheet_names) >= 2:
                for i in range(len(sheet_names)):
                    for j in range(i + 1, len(sheet_names)):
                        sheet1, sheet2 = sheet_names[i], sheet_names[j]
                        join_result = tools.suggest_join_keys(sheet1, sheet2)
                        if join_result.success and join_result.data:
                            # Test the best join suggestion
                            best_join = join_result.data[0]
                            if best_join["overlap_pct"] > 30:
                                test_result = tools.test_join_quality(
                                    sheet1, sheet2, 
                                    best_join["col1"], best_join["col2"]
                                )
                                if test_result.success:
                                    insights["join_suggestions"].append({
                                        "sheet1": sheet1,
                                        "sheet2": sheet2,
                                        "column1": best_join["col1"],
                                        "column2": best_join["col2"],
                                        "overlap_pct": best_join["overlap_pct"],
                                        "match_quality": test_result.data
                                    })
                                    tools_called.append(f"test_join_quality({sheet1}, {sheet2})")
            
            # ===== ITERATION 2: Profile key sheets =====
            logger.info("AI Exploration - Iteration 2: Data profiling")
            
            # Profile the first sheet (primary data)
            if sheet_names:
                primary_sheet = sheet_names[0]
                profile_result = tools.profile_full_dataset(primary_sheet)
                if profile_result.success:
                    insights["primary_sheet_profile"] = profile_result.data
                    tools_called.append(f"profile_full_dataset({primary_sheet})")
            
            # Store exploration results
            state["_exploration_insights"] = insights
            state["_tools_called"] = tools_called
            
            # Log summary
            logger.info(f"AI Exploration complete: {len(tools_called)} tool calls")
            logger.info(f"  - Sheets analyzed: {len(sheet_names)}")
            logger.info(f"  - Join suggestions: {len(insights['join_suggestions'])}")
            logger.info(f"  - Time series columns: {len(insights['time_series_columns'])}")
            logger.info(f"  - Quality issues: {len(insights['data_quality_issues'])}")
            
            state["messages"].append(
                f"AI exploration complete: analyzed {len(sheet_names)} sheets with {len(tools_called)} tool calls"
            )
            
        except Exception as e:
            state["errors"].append(f"Exploration error: {str(e)}")
            logger.error(f"Data exploration failed: {e}")
            state["_exploration_insights"] = {}
            state["_tools_called"] = []
        
        return state
    
    async def analyze_join_strategy_multiphase(
        self,
        sheets: Dict[str, pd.DataFrame],
        file_contexts: List[Dict[str, str]],
        global_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Multi-Phase Reasoning for intelligent join strategy.
        
        Phases:
        1. Context Injection - Use file_context and global_description
        2. Deep Inspection - Value distributions, ID column patterns
        3. AI Proposal - AI suggests 2-3 potential join keys
        4. Validation - Test each key and select best match
        
        Returns:
            Join strategy with confidence_score and validation_results
        """
        import json
        
        if len(sheets) < 2 or not self.model:
            return {"should_join": False, "reason": "Insufficient sheets or no AI model"}
        
        tools = DataTools(
            dataframes=sheets,
            file_contexts=file_contexts,
            global_description=global_description
        )
        
        sheet_names = list(sheets.keys())
        
        # ===== PHASE 1: Context Injection =====
        logger.info("Join Analysis - Phase 1: Context injection")
        
        context_info = {}
        for sheet_name in sheet_names:
            # Find matching file context
            sheet_context = None
            for fc in file_contexts:
                if fc.get("file_name") and (
                    fc["file_name"] in sheet_name or 
                    sheet_name in fc.get("file_name", "")
                ):
                    sheet_context = fc.get("file_context")
                    break
            
            context_info[sheet_name] = {
                "user_context": sheet_context,
                "row_count": len(sheets[sheet_name]),
                "columns": list(sheets[sheet_name].columns)
            }
        
        # ===== PHASE 2: Deep Inspection =====
        logger.info("Join Analysis - Phase 2: Deep inspection")
        
        deep_inspection = {}
        for sheet_name in sheet_names:
            df = sheets[sheet_name]
            
            # Get column types
            types_result = tools.get_column_types(sheet_name)
            column_types = types_result.data if types_result.success else {}
            
            # Identify potential ID/Key columns
            potential_keys = []
            for col in df.columns:
                col_lower = str(col).lower()
                # Check naming patterns
                is_id_pattern = any(pattern in col_lower for pattern in [
                    'id', 'key', 'code', 'ticker', 'symbol', 'sku', 'number', 'num', 'no'
                ])
                
                # Check uniqueness ratio
                unique_ratio = df[col].nunique() / len(df) if len(df) > 0 else 0
                
                if is_id_pattern or unique_ratio > 0.5:
                    # Get sample values
                    unique_result = tools.get_unique_values(sheet_name, col, limit=5)
                    sample_values = unique_result.data.get("unique_values", []) if unique_result.success else []
                    
                    potential_keys.append({
                        "column": col,
                        "type": column_types.get(col, "unknown"),
                        "unique_count": df[col].nunique(),
                        "unique_ratio": round(unique_ratio, 2),
                        "is_id_pattern": is_id_pattern,
                        "sample_values": sample_values[:3]
                    })
            
            deep_inspection[sheet_name] = {
                "column_types": column_types,
                "potential_keys": potential_keys[:5],  # Top 5 candidates
                "sample_data": df.head(3).to_dict(orient='records')
            }
        
        # ===== PHASE 3: AI Proposal =====
        logger.info("Join Analysis - Phase 3: AI proposal")
        
        # Build comprehensive prompt with context
        context_section = ""
        if global_description:
            context_section = f"DASHBOARD PURPOSE: {global_description}\n\n"
        
        sheets_description = ""
        for sheet_name, info in context_info.items():
            user_ctx = info.get("user_context") or "No context provided"
            inspection = deep_inspection.get(sheet_name, {})
            potential_keys = inspection.get("potential_keys", [])
            
            keys_str = "\n".join([
                f"    - {k['column']} ({k['type']}, {k['unique_count']} unique, examples: {k['sample_values']})"
                for k in potential_keys
            ]) or "    - No obvious key columns"
            
            sheets_description += f"""
SHEET: {sheet_name}
  User Context: {user_ctx}
  Rows: {info['row_count']}
  Potential Key Columns:
{keys_str}
  Sample Data: {inspection.get('sample_data', [])}

"""
        
        prompt = f"""{context_section}Analyze these sheets and propose 2-3 potential join key pairs:

{sheets_description}

Based on the user context and data patterns, identify the BEST columns to join these sheets.

Consider:
1. Column naming patterns (e.g., 'ticker' in one sheet might match 'symbol' in another)
2. Data types should be compatible
3. The user's context hints (e.g., "portfolio" and "transactions" likely share a stock identifier)

Return a JSON object with your proposals - I will TEST each one to find the best match:
{{
    "proposals": [
        {{
            "sheet1": "sheet_name",
            "sheet2": "sheet_name",
            "column1": "column_name",
            "column2": "column_name",
            "reasoning": "Why these columns should match"
        }}
    ],
    "primary_recommendation": 0, // index of best proposal
    "overall_reasoning": "High-level explanation of join strategy"
}}

JSON response only:"""

        ai_proposals = []
        try:
            response = await self.model.generate_content_async(prompt)
            result_text = response.text.strip()
            
            # Extract JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                ai_response = json.loads(json_match.group())
                ai_proposals = ai_response.get("proposals", [])
                logger.info(f"AI proposed {len(ai_proposals)} join strategies")
        except Exception as e:
            logger.warning(f"AI proposal failed: {e}")
        
        # ===== PHASE 4: Validation Loop =====
        logger.info("Join Analysis - Phase 4: Validation loop")
        
        validation_results = []
        best_join = None
        best_match_pct = 0
        
        for i, proposal in enumerate(ai_proposals):
            sheet1 = proposal.get("sheet1")
            sheet2 = proposal.get("sheet2")
            col1 = proposal.get("column1")
            col2 = proposal.get("column2")
            
            if not all([sheet1, sheet2, col1, col2]):
                continue
            
            if sheet1 not in sheets or sheet2 not in sheets:
                continue
            
            # Test join quality
            quality = tools.test_join_quality(sheet1, sheet2, col1, col2)
            
            if quality.success:
                match_pct = min(
                    quality.data.get("match_pct_sheet1", 0),
                    quality.data.get("match_pct_sheet2", 0)
                )
                
                validation_results.append({
                    "proposal_index": i,
                    "columns": f"{sheet1}.{col1} = {sheet2}.{col2}",
                    "match_pct": match_pct,
                    "matched_count": quality.data.get("matched_count", 0),
                    "recommendation": quality.data.get("recommendation", ""),
                    "ai_reasoning": proposal.get("reasoning", "")
                })
                
                logger.info(f"Tested {col1}={col2}: {match_pct}% match")
                
                if match_pct > best_match_pct:
                    best_match_pct = match_pct
                    best_join = {
                        "left": sheet1,
                        "right": sheet2,
                        "left_col": col1,
                        "right_col": col2,
                        "match_pct": match_pct,
                        "quality_data": quality.data
                    }
        
        # Build final result
        if best_join and best_match_pct >= 50:
            confidence_score = min(100, best_match_pct + 10)  # Bonus for validation
            
            return {
                "should_join": True,
                "joins": [best_join],
                "confidence_score": confidence_score,
                "validation_results": validation_results,
                "selected_join": {
                    "columns": f"{best_join['left']}.{best_join['left_col']} = {best_join['right']}.{best_join['right_col']}",
                    "match_pct": best_match_pct,
                    "reason": f"Highest validated match ({best_match_pct}%) among {len(ai_proposals)} AI proposals"
                },
                "ai_proposals_count": len(ai_proposals),
                "phases_completed": ["context_injection", "deep_inspection", "ai_proposal", "validation"]
            }
        elif best_join and best_match_pct >= 30:
            # Low confidence warning
            return {
                "should_join": True,
                "joins": [best_join],
                "confidence_score": best_match_pct,
                "validation_results": validation_results,
                "warning": f"Low match quality ({best_match_pct}%). Consider keeping sheets separate.",
                "selected_join": {
                    "columns": f"{best_join['left']}.{best_join['left_col']} = {best_join['right']}.{best_join['right_col']}",
                    "match_pct": best_match_pct
                }
            }
        else:
            return {
                "should_join": False,
                "confidence_score": 0,
                "validation_results": validation_results,
                "reason": "No join key achieved sufficient match quality (>30%)",
                "ai_proposals_count": len(ai_proposals)
            }
    
    async def _detect_schema_drift(self, state: AgentState) -> AgentState:
        """Detect schema changes from previous version."""
        try:
            # Build current schema from loaded sheets
            current_schema = {}
            for name, records in state["sheets"].items():
                if records:
                    df = pd.DataFrame(records)
                    current_schema[name] = self.schema_mapper.extract_schema(df)
            
            state["current_schema"] = current_schema
            
            # Compare with previous schema
            if state["previous_schema"]:
                drift_reports = self.schema_mapper.detect_drift(
                    state["previous_schema"],
                    current_schema
                )
                
                state["drift_reports"] = [r.to_dict() for r in drift_reports]
                state["schema_drift_detected"] = any(r.has_drift for r in drift_reports)
                
                if state["schema_drift_detected"]:
                    state["messages"].append("Schema drift detected")
            else:
                state["drift_reports"] = []
                state["schema_drift_detected"] = False
                
        except Exception as e:
            state["errors"].append(f"Schema detection error: {str(e)}")
            logger.error(f"Schema detection failed: {e}")
        
        return state
    
    async def _clean_data(self, state: AgentState) -> AgentState:
        """Clean and process the data."""
        try:
            result = await self.data_processor.process(state["file_bytes"])
            
            # Store cleaned data
            if result.unified_df is not None:
                state["unified_data"] = make_serializable(result.unified_df.to_dict(orient='records'))
            
            # Update sheets with cleaned versions
            cleaned_sheets = {}
            for name, df in result.sheets.items():
                cleaned_sheets[name] = make_serializable(df.to_dict(orient='records'))
            state["sheets"] = cleaned_sheets
            
            state["messages"].extend(result.cleaning_log)
            state["errors"].extend(result.errors)
            
        except Exception as e:
            state["errors"].append(f"Cleaning error: {str(e)}")
            logger.error(f"Data cleaning failed: {e}")
        
        return state
    
    async def _analyze_data(self, state: AgentState) -> AgentState:
        """Analyze data structure with file contexts for visualization suggestions."""
        try:
            # Get data summary for AI analysis
            data = state.get("unified_data") or list(state["sheets"].values())[0] if state["sheets"] else []
            
            if not data:
                return state
            
            df = pd.DataFrame(data)
            
            # Prepare data summary
            summary = {
                "columns": list(df.columns),
                "dtypes": {col: str(df[col].dtype) for col in df.columns},
                "row_count": len(df),
                "sample": df.head(3).to_dict(orient='records'),
                "numeric_cols": [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])],
                "categorical_cols": [col for col in df.columns if df[col].dtype == 'object'],
                "date_cols": [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
            }
            
            # Build context section for AI from global description and file contexts
            context_notes = []
            if state.get("global_description"):
                context_notes.append(f"Dashboard Purpose: {state['global_description']}")
            
            for file_info in state.get("_file_contexts", []):
                if file_info.get("file_context"):
                    context_notes.append(f"File '{file_info['file_name']}': {file_info['file_context']}")
            
            # Store context for chart generation
            summary["user_context"] = "\n".join(context_notes) if context_notes else None
            
            # Store for chart generation
            state["_data_summary"] = summary
            state["messages"].append("Data analysis complete")
            
        except Exception as e:
            state["errors"].append(f"Analysis error: {str(e)}")
            logger.error(f"Data analysis failed: {e}")
        
        return state
    
    async def _generate_charts(self, state: AgentState) -> AgentState:
        """Generate chart configurations using AI with exploration insights."""
        try:
            data = state.get("unified_data") or list(state["sheets"].values())[0] if state["sheets"] else []
            
            if not data:
                state["chart_data"] = {}
                state["chart_suggestions"] = []
                return state
            
            df = pd.DataFrame(data)
            
            # Generate chart suggestions with AI
            summary = state.get("_data_summary", {})
            exploration = state.get("_exploration_insights", {})
            
            # Build context section for the prompt
            context_section = ""
            user_context = summary.get("user_context")
            if user_context:
                context_section = f"""USER CONTEXT (use this to understand column relationships and joining keys):
{user_context}

"""
            
            # Add exploration insights to prompt
            exploration_section = ""
            if exploration:
                exploration_parts = []
                
                # Join suggestions
                if exploration.get("join_suggestions"):
                    joins = exploration["join_suggestions"]
                    join_info = [f"  - {j['sheet1']} can join with {j['sheet2']} on {j['column1']}={j['column2']} ({j['overlap_pct']}% match)" for j in joins[:3]]
                    exploration_parts.append("JOIN OPPORTUNITIES:\n" + "\n".join(join_info))
                
                # Time series columns
                if exploration.get("time_series_columns"):
                    ts_cols = exploration["time_series_columns"]
                    ts_info = [f"  - {t['sheet']}.{t['column']} ({t.get('frequency', 'unknown')} frequency)" for t in ts_cols[:3]]
                    exploration_parts.append("TIME SERIES COLUMNS (good for line charts):\n" + "\n".join(ts_info))
                
                # Data quality issues
                if exploration.get("data_quality_issues"):
                    quality_info = exploration["data_quality_issues"][:3]
                    exploration_parts.append("DATA QUALITY NOTES:\n" + "\n".join([f"  - {q}" for q in quality_info]))
                
                if exploration_parts:
                    exploration_section = "AI EXPLORATION FINDINGS:\n" + "\n\n".join(exploration_parts) + "\n\n"
            
            prompt = f"""{context_section}{exploration_section}Analyze this data and suggest 3-4 effective visualizations:

Columns: {summary.get('columns', [])}
Data Types: {summary.get('dtypes', {})}
Row Count: {summary.get('row_count', 0)}
Numeric columns: {summary.get('numeric_cols', [])}
Categorical columns: {summary.get('categorical_cols', [])}
Sample:
{summary.get('sample', [])}

IMPORTANT: Use the AI exploration findings above to make smarter chart choices:
- If time series columns exist, prefer LINE charts for trends
- If join opportunities exist, consider charts that combine data from multiple sources
- Avoid columns with high null percentages for key metrics

Return a JSON array of chart configurations. For each chart, explain WHY you chose it:
[
    {{
        "id": "chart_1",
        "type": "bar|line|pie|area|scatter",
        "title": "Chart Title",
        "x_axis": "column_name or null",
        "y_axis": "column_name",
        "data_key": "column for values",
        "color": "#14FF6E",
        "reasoning": "Brief explanation why this chart type is ideal for this data"
    }}
]

Focus on meaningful business insights. Be specific in your reasoning. JSON response only:"""

            response = await self.model.generate_content_async(prompt)
            result_text = response.text.strip()
            
            # Parse JSON from response
            import json
            import re
            
            json_match = re.search(r'\[[\s\S]*\]', result_text)
            if json_match:
                charts = json.loads(json_match.group())
                state["chart_suggestions"] = charts
            else:
                # Default chart suggestions
                state["chart_suggestions"] = self._default_charts(df)
            
            # Prepare chart data (aggregated values for each suggested chart)
            chart_data = {"raw_data": make_serializable(data[:1000])}  # Limit to 1000 rows for frontend
            
            for chart in state["chart_suggestions"]:
                chart_id = chart.get("id", f"chart_{len(chart_data)}")
                x_col = chart.get("x_axis")
                y_col = chart.get("y_axis") or chart.get("data_key")
                
                if y_col and y_col in df.columns:
                    if x_col and x_col in df.columns:
                        # Grouped data
                        grouped = df.groupby(x_col)[y_col].sum().reset_index()
                        chart_data[chart_id] = make_serializable(grouped.to_dict(orient='records'))
                    else:
                        # Simple series
                        chart_data[chart_id] = make_serializable(df[[y_col]].to_dict(orient='records'))
            
            state["chart_data"] = chart_data
            state["messages"].append(f"Generated {len(state['chart_suggestions'])} chart suggestions")
            
        except Exception as e:
            state["errors"].append(f"Chart generation error: {str(e)}")
            logger.error(f"Chart generation failed: {e}")
            
            # Fallback
            data = state.get("unified_data") or []
            state["chart_data"] = {"raw_data": data[:1000] if data else []}
            state["chart_suggestions"] = []
        
        return state
    
    def _default_charts(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate default chart suggestions based on data structure."""
        charts = []
        
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        categorical_cols = [col for col in df.columns if df[col].dtype == 'object']
        
        # Bar chart for first categorical + numeric combo
        if categorical_cols and numeric_cols:
            charts.append({
                "id": "chart_1",
                "type": "bar",
                "title": f"{numeric_cols[0]} by {categorical_cols[0]}",
                "x_axis": categorical_cols[0],
                "y_axis": numeric_cols[0],
                "color": "#14FF6E",
                "reasoning": f"Bar chart effectively compares {numeric_cols[0]} values across different {categorical_cols[0]} categories."
            })
        
        # Line chart if there are multiple numeric columns
        if len(numeric_cols) >= 2:
            charts.append({
                "id": "chart_2", 
                "type": "line",
                "title": f"{numeric_cols[0]} Trend",
                "data_key": numeric_cols[0],
                "color": "#14FF6E",
                "reasoning": f"Line chart shows trends and patterns in {numeric_cols[0]} over the data series."
            })
        
        # Pie chart for first categorical column
        if categorical_cols:
            charts.append({
                "id": "chart_3",
                "type": "pie",
                "title": f"{categorical_cols[0]} Distribution",
                "data_key": categorical_cols[0],
                "color": "#14FF6E",
                "reasoning": f"Pie chart visualizes the proportional distribution of {categorical_cols[0]} categories."
            })
        
        return charts
    
    async def process_excel(
        self,
        file_bytes: bytes,
        previous_schema: Optional[Dict[str, Dict[str, str]]] = None,
        accept_schema_drift: bool = True
    ) -> ProcessingOutput:
        """
        Process an Excel file through the full agent pipeline.
        
        Args:
            file_bytes: Raw Excel file bytes
            previous_schema: Previous column schema for drift detection
            accept_schema_drift: Whether to auto-accept schema changes
            
        Returns:
            ProcessingOutput with results
        """
        # Initialize state
        initial_state: AgentState = {
            "file_bytes": file_bytes,
            "previous_schema": previous_schema or {},
            "accept_schema_drift": accept_schema_drift,
            "sheets": {},
            "unified_data": None,
            "current_schema": {},
            "drift_reports": [],
            "schema_drift_detected": False,
            "chart_suggestions": [],
            "chart_data": {},
            "messages": [],
            "errors": [],
        }
        
        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)
        
        # Build output
        return ProcessingOutput(
            sheet_names=list(final_state["sheets"].keys()),
            new_schema=final_state["current_schema"],
            schema_drift_detected=final_state["schema_drift_detected"],
            schema_drift_info=final_state["drift_reports"] if final_state["schema_drift_detected"] else None,
            chart_data=final_state["chart_data"],
            suggested_charts=final_state["chart_suggestions"],
            message="; ".join(final_state["messages"]) if final_state["messages"] else "Processing complete"
        )
    
    async def process_multiple_files(
        self,
        files_data: List[Dict[str, Any]],
        global_description: Optional[str] = None,
        previous_schema: Optional[Dict[str, Dict[str, str]]] = None,
        accept_schema_drift: bool = True
    ) -> ProcessingOutput:
        """
        Process multiple Excel files with context for intelligent joining.
        
        Args:
            files_data: List of file info dicts with keys:
                - file_id: Google Drive file ID
                - file_name: Original file name
                - file_bytes: Raw file bytes
                - file_context: Optional user context about the file
            global_description: User context for the entire dashboard
            previous_schema: Previous column schema for drift detection
            accept_schema_drift: Whether to auto-accept schema changes
            
        Returns:
            ProcessingOutput with results from all files combined
        """
        import io
        
        # If only one file, use the simpler single-file method with context
        if len(files_data) == 1:
            file_info = files_data[0]
            initial_state: AgentState = {
                "file_bytes": file_info["file_bytes"],
                "global_description": global_description,
                "previous_schema": previous_schema or {},
                "accept_schema_drift": accept_schema_drift,
                "sheets": {},
                "unified_data": None,
                "current_schema": {},
                "drift_reports": [],
                "schema_drift_detected": False,
                "chart_suggestions": [],
                "chart_data": {},
                "messages": [],
                "errors": [],
                "_file_contexts": [{"file_name": file_info["file_name"], "file_context": file_info.get("file_context")}],
            }
            
            final_state = await self.graph.ainvoke(initial_state)
            
            return ProcessingOutput(
                sheet_names=list(final_state["sheets"].keys()),
                new_schema=final_state["current_schema"],
                schema_drift_detected=final_state["schema_drift_detected"],
                schema_drift_info=final_state["drift_reports"] if final_state["schema_drift_detected"] else None,
                chart_data=final_state["chart_data"],
                suggested_charts=final_state["chart_suggestions"],
                message="; ".join(final_state["messages"]) if final_state["messages"] else "Processing complete"
            )
        
        # Multi-file processing: load all sheets from all files
        all_sheets = {}
        file_contexts = []
        all_sheet_names = []
        
        for file_info in files_data:
            try:
                sheets = self.data_processor.load_all_sheets(file_info["file_bytes"])
                # Prefix sheet names with file name to avoid collisions
                file_prefix = file_info["file_name"].rsplit(".", 1)[0]  # Remove extension
                for sheet_name, df in sheets.items():
                    prefixed_name = f"{file_prefix}_{sheet_name}"
                    all_sheets[prefixed_name] = make_serializable(df.to_dict(orient='records'))
                    all_sheet_names.append(prefixed_name)
                
                # Store file context
                file_contexts.append({
                    "file_name": file_info["file_name"],
                    "file_context": file_info.get("file_context")
                })
                
            except Exception as e:
                logger.error(f"Failed to load file {file_info['file_name']}: {e}")
        
        if not all_sheets:
            return ProcessingOutput(
                sheet_names=[],
                new_schema={},
                schema_drift_detected=False,
                schema_drift_info=None,
                chart_data={},
                suggested_charts=[],
                message="No data could be loaded from any files"
            )
        
        # Combine all data for unified processing
        all_records = []
        for records in all_sheets.values():
            all_records.extend(records)
        
        # Build state with combined data
        initial_state: AgentState = {
            "file_bytes": b"",  # Not used in multi-file mode
            "files_data": files_data,
            "global_description": global_description,
            "previous_schema": previous_schema or {},
            "accept_schema_drift": accept_schema_drift,
            "sheets": all_sheets,
            "unified_data": all_records[:10000] if all_records else None,  # Limit for performance
            "current_schema": {},
            "drift_reports": [],
            "schema_drift_detected": False,
            "chart_suggestions": [],
            "chart_data": {},
            "messages": [f"Loaded {len(files_data)} files with {len(all_sheets)} total sheets"],
            "errors": [],
            "_file_contexts": file_contexts,
        }
        
        # Run exploration, analyze_data and generate_charts
        # This enables the AI reasoning loop for multi-file dashboards
        state = await self._explore_data(initial_state)  # NEW: Explore data first
        state = await self._analyze_data(state)
        state = await self._generate_charts(state)
        
        return ProcessingOutput(
            sheet_names=all_sheet_names,
            new_schema=state.get("current_schema", {}),
            schema_drift_detected=state.get("schema_drift_detected", False),
            schema_drift_info=state.get("drift_reports") if state.get("schema_drift_detected") else None,
            chart_data=state.get("chart_data", {}),
            suggested_charts=state.get("chart_suggestions", []),
            message="; ".join(state.get("messages", [])) if state.get("messages") else "Multi-file processing complete"
        )

