import pandas as pd
import os
from daily_report import render_report_image, REPORT_DIR

def main():
    print("--- 📸 Generating Historical Report Cards ---")
    
    # Load the perfectly rebuilt history CSV
    df = pd.read_csv("wealth_history.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Extract just the Date (YYYY-MM-DD)
    df['date'] = df['timestamp'].dt.date
    
    # Magic: Group by the date, and grab the index of the LATEST timestamp for each day
    # This guarantees we only generate the report using the final state of that day!
    daily_final_indices = df.groupby('date')['timestamp'].idxmax()
    daily_final_df = df.loc[daily_final_indices]
    
    total_days = len(daily_final_df)
    print(f"Found {total_days} unique days. Rendering images...")
    
    for _, row in daily_final_df.iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        filepath = os.path.join(REPORT_DIR, f"report_{date_str}.png")
        
        # Convert the Pandas Series row into a standard Python Dictionary
        w = row.to_dict()
        
        # Render the image using the logic we imported from daily_report.py
        render_report_image(w, filepath, date_str)
        print(f"Generated: report_{date_str}.png")
        
    print("\n✅ Done! All historical frames are sitting in your daily_reports folder.")

if __name__ == "__main__":
    main()