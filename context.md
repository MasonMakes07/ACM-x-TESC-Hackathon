EARTH Watch

IDEA 1 — EARTHWATCH: An autonomous climate-threat intelligence system
My favorite if you want to combine your friend's climate idea with a genuinely useful multi-agent product.
The problem
Climate-related disasters rarely result from a single isolated measurement. Unusual ocean temperatures, rainfall changes, soil moisture, and other indicators can interact, while the resulting impacts vary by region.
Existing scientific forecasts are valuable, but interpreting multiple sources and translating them into local decisions can be difficult.
The product
EarthWatch is a system that monitors environmental signals and independently investigates unusual patterns.
Imagine opening a dashboard and seeing:
PACIFIC ANOMALY DETECTED
Sea surface temperatures are deviating from the historical baseline in a monitored region.
Potential concern: Changes in rainfall patterns affecting coastal Peru.
Investigation status: 3 data sources reviewed. 2 support the signal; 1 is inconclusive.
Next step: Investigate rainfall outlooks and potential flooding exposure in northern Peru.
The interface then lets the user explore the evidence and see how the system reached its conclusion.
How the bots work
Bot
Responsibility
Output
Ocean Sentinel
Analyzes sea surface temperature and historical anomalies
Anomaly score
Climate Investigator
Checks additional datasets and relevant scientific information
Evidence report
Regional Impact Analyst
Examines potential consequences for a selected region
Impact assessment
Briefing Bot
Summarizes findings, uncertainty, and recommended monitoring actions
Interactive threat briefing

What makes it technically impressive?
Don't simply ask Grok whether El Niño is coming.
Build a small but real data pipeline:
Retrieve environmental data from an established scientific source.
Calculate anomalies against a historical baseline.
Detect changes using a statistical method.
Ask the investigator agent to retrieve independent supporting evidence.
Produce a structured assessment that distinguishes measured facts from hypotheses.
Display the results on a geographic dashboard.
For the demo, you could replay a historical event and show whether your system identifies its development and assembles a useful briefing.
The important limitation
Detecting an anomaly is not the same as predicting El Niño. ENSO forecasting requires appropriate ocean–atmosphere indicators and validation against established forecasting methods. Don't claim predictive accuracy you haven't measured.
A credible initial version would detect unusual environmental conditions and investigate their possible implications. You could expand toward forecasting if time permits.
How to make it more original
Focus on a specific question:
"How might developing climate anomalies affect communities and infrastructure in coastal Peru?"
That is a more compelling product than a generic global climate dashboard. It gives the project a real user, a meaningful geographic focus, and an outcome beyond visualizing data.
Potential: High usefulness, strong visuals, and good technical depth. The main risk is that the climate analysis becomes too broad to implement convincingly.
