Steps to run the 14-day signal-bias deep dive on EC2

1) SSH to EC2 (example — replace path/IP if different):

   ssh -i "C:\Users\bigso\Downloads\opticore-key.pem" ubuntu@52.90.60.32

2) Run the prepared report script (writes CSVs + PNGs):

   cd ~/opticore-bot
   python3 scripts/signal_bias_report.py --db /home/ubuntu/opticore-bot/data/trading_bot.db --outdir /home/ubuntu/opticore-bot/reports/signal_bias

3) (Optional) Run the quick CLI bias checker:

   python3 check_signal_bias.py

4) Download artifacts to your local machine (example using scp):

   scp -i "C:\Users\bigso\Downloads\opticore-key.pem" ubuntu@52.90.60.32:/home/ubuntu/opticore-bot/reports/signal_bias/* "C:\Users\bigso\Downloads\ML\reports\signal_bias\"

5) Open the interactive notebook locally (after copying CSVs):

   jupyter lab notebooks/signal_bias_analysis.ipynb

What I will deliver if you run step 2 (or allow me to run it):
- CSVs: `signal_counts_14d.csv`, `per_symbol_bias.csv`, `daily_signal_counts.csv`
- PNG charts: `daily_signal_counts.png`, `per_symbol_bias_top20.png`, `rolling_bias_7d.png` (+ confidence chart if available)
- Interactive notebook `notebooks/signal_bias_analysis.ipynb` to reproduce/extend the analysis

Tell me once artifacts are uploaded here or paste the `per_symbol_bias.csv` and I'll generate the full report and recommended mitigations.