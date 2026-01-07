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
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("load_sheets", self._load_sheets)
        workflow.add_node("detect_schema_drift", self._detect_schema_drift)
        workflow.add_node("clean_data", self._clean_data)
        workflow.add_node("analyze_data", self._analyze_data)
        workflow.add_node("generate_charts", self._generate_charts)
        
        # Add edges
        workflow.set_entry_point("load_sheets")
        workflow.add_edge("load_sheets", "detect_schema_drift")
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
        """Generate chart configurations using AI."""
        try:
            data = state.get("unified_data") or list(state["sheets"].values())[0] if state["sheets"] else []
            
            if not data:
                state["chart_data"] = {}
                state["chart_suggestions"] = []
                return state
            
            df = pd.DataFrame(data)
            
            # Generate chart suggestions with AI
            summary = state.get("_data_summary", {})
            
            # Build context section for the prompt
            context_section = ""
            user_context = summary.get("user_context")
            if user_context:
                context_section = f"""USER CONTEXT (use this to understand column relationships and joining keys):
{user_context}

"""
            
            prompt = f"""{context_section}Analyze this data and suggest 3-4 effective visualizations:

Columns: {summary.get('columns', [])}
Data Types: {summary.get('dtypes', {})}
Row Count: {summary.get('row_count', 0)}
Numeric columns: {summary.get('numeric_cols', [])}
Categorical columns: {summary.get('categorical_cols', [])}
Sample:
{summary.get('sample', [])}

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
        
        # Skip load_sheets and clean_data, go directly to analysis
        # Run analyze_data and generate_charts manually
        state = await self._analyze_data(initial_state)
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

