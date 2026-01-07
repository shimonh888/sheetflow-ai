import pandas as pd
import duckdb
from typing import Dict, List, Any, Optional

class DataTools:
    """ארגז הכלים של ה-AI לחקירת נתונים בתוך ה-Sandbox."""
    
    def __init__(self, dataframes: Dict[str, pd.DataFrame]):
        # עבודה על עותקים כדי למנוע שינוי של נתוני המקור
        self.dfs = {name: df.copy() for name, df in dataframes.items()}
        self.con = duckdb.connect(database=':memory:')
        
        # רישום ה-DataFrames כטבלאות ב-DuckDB
        for name, df in self.dfs.items():
            clean_name = name.replace(" ", "_").replace(".", "_")
            self.con.register(clean_name, df)

    def list_dashboard_files(self, file_metadata: List[Dict]) -> List[Dict]:
        """מציגה ל-AI אילו קבצים קיימים ומה המשתמש כתב עליהם."""
        return file_metadata

    def get_column_types(self, table_name: str) -> Dict[str, str]:
        """מחזירה את סוגי הנתונים של כל עמודה כדי למנוע שגיאות חישוב."""
        if table_name not in self.dfs:
            return {"error": "Table not found"}
        return self.dfs[table_name].dtypes.apply(lambda x: x.name).to_dict()

    def test_join_quality(self, left_table: str, right_table: str, on_column: str) -> Dict[str, Any]:
        """הכלי החשוב ביותר: בודק כמה שורות באמת מתחברות בין שני קבצים לפני הביצוע."""
        try:
            query = f"""
            SELECT 
                COUNT(*) as total_left,
                COUNT(rt.{on_column}) as matched_rows
            FROM {left_table} lt
            LEFT JOIN {right_table} rt ON lt.{on_column} = rt.{on_column}
            """
            result = self.con.execute(query).df().iloc[0]
            match_pct = (result['matched_rows'] / result['total_left']) * 100 if result['total_left'] > 0 else 0
            return {
                "match_percentage": round(match_pct, 2),
                "matched_rows": int(result['matched_rows']),
                "total_rows": int(result['total_left'])
            }
        except Exception as e:
            return {"error": str(e)}

    def run_sql_query(self, sql: str) -> List[Dict]:
        """מאפשר ל-AI להריץ שאילתות מורכבות כדי לחלץ תובנות."""
        try:
            # הגבלה ל-100 שורות כדי למנוע עומס ב-Token usage
            return self.con.execute(sql).df().head(100).to_dict(orient='records')
        except Exception as e:
            return {"error": str(e)}