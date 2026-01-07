import pandas as pd
import duckdb
import re
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DataTools:
    """
    ארגז הכלים המאוחד של SheetFlow AI.
    מאפשר לבינה המלאכותית לחקור, לנקות ולחבר נתונים פיננסיים בתוך Sandbox בטוח.
    """
    
    def __init__(self, dataframes: Dict[str, pd.DataFrame]):
        # עבודה על עותקים כדי למנוע שינוי של נתוני המקור בטעות
        self.dfs = {name: df.copy() for name, df in dataframes.items()}
        self.con = duckdb.connect(database=':memory:')
        
        # רישום ה-DataFrames כטבלאות ב-DuckDB עם שמות נקיים ל-SQL
        for name, df in self.dfs.items():
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
            try:
                self.con.register(clean_name, df)
                logger.info(f"Registered table: {clean_name}")
            except Exception as e:
                logger.error(f"Failed to register {name}: {e}")

    # --- כלי חקירה מבניים ---

    def list_dashboard_files(self, file_metadata: List[Dict]) -> List[Dict]:
        """מציגה ל-AI אילו קבצים קיימים ומה ההקשר (Context) שהמשתמש סיפק להם."""
        return file_metadata

    def get_column_types(self, table_name: str) -> Dict[str, str]:
        """מחזירה את סוגי הנתונים של כל עמודה כדי למנוע שגיאות חישוב ב-AI."""
        if table_name not in self.dfs:
            return {"error": f"Table '{table_name}' not found"}
        return self.dfs[table_name].dtypes.apply(lambda x: x.name).to_dict()

    def preview_data(self, table_name: str, n: int = 5) -> List[Dict]:
        """מחזירה דגימה של השורות הראשונות כדי להבין את מבנה התוכן."""
        if table_name not in self.dfs:
            return {"error": "Table not found"}
        return self.dfs[table_name].head(n).to_dict(orient='records')

    # --- כלי ניתוח פיננסי ואיכות נתונים ---

    def identify_currency_columns(self, table_name: str) -> List[str]:
        """מזהה עמודות פיננסיות (כמו Market Value) המכילות סימני $ או ₪ המצריכים ניקוי."""
        if table_name not in self.dfs:
            return []
        df = self.dfs[table_name]
        currency_cols = []
        for col in df.columns:
            # דגימת הערכים שאינם ריקים
            sample = df[col].dropna().astype(str).head(10)
            if any(sample.str.contains(r'[\$\,₪]', regex=True)):
                currency_cols.append(col)
        return currency_cols

    def test_join_quality(self, left_table: str, right_table: str, on_column: str) -> Dict[str, Any]:
        """
        בודק את איכות החיבור (Join) בין שני קבצים (למשל Holdings ו-Transactions).
        מחשב אחוזי התאמה לפי עמודת מפתח (כמו Ticker).
        """
        try:
            query = f"""
            SELECT 
                COUNT(lt.{on_column}) as total_left,
                COUNT(rt.{on_column}) as matched_rows,
                COUNT(DISTINCT lt.{on_column}) as unique_keys_left
            FROM {left_table} lt
            LEFT JOIN {right_table} rt ON lt.{on_column} = rt.{on_column}
            """
            res = self.con.execute(query).df().iloc[0]
            
            total = int(res['total_left'])
            matched = int(res['matched_rows'])
            match_pct = (matched / total * 100) if total > 0 else 0
            
            return {
                "match_percentage": round(match_pct, 2),
                "matched_rows": matched,
                "total_rows": total,
                "unique_keys_found": int(res['unique_keys_left']),
                "status": "High Quality" if match_pct > 80 else "Low Quality/No Match"
            }
        except Exception as e:
            return {"error": str(e)}

    # --- כלי ביצוע ותובנות ---

    def run_sql_query(self, sql: str) -> List[Dict]:
        """מריץ שאילתת SQL (דרך DuckDB) על כלל הטבלאות בזיכרון ומחזיר עד 100 שורות."""
        try:
            return self.con.execute(sql).df().head(100).to_dict(orient='records')
        except Exception as e:
            return {"error": str(e)}

    def run_portfolio_analysis(self, sql_query: str) -> List[Dict]:
        """כלי ייעודי להרצת חישובים פיננסיים מורכבים כמו P&L משוקלל או ניתוח R/R."""
        # בפועל עושה שימוש באותו מנוע SQL אך מיועד ללוגיקה עסקית
        return self.run_sql_query(sql_query)