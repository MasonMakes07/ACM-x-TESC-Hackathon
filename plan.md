WORLDWIDE SCOPE UPDATE - 2026-10-24
The product now supports locations worldwide. The original Peru-focused proposal
below is retained as historical project context and a replay case study. Its
geographic restrictions are superseded by the following requirements:
- Default to worldwide monitoring with all countries/territories searchable.
- Let users select a place within any country, or enter arbitrary coordinates.
- Retrieve local ERA5 air temperature and precipitation with local timezones,
  source/coordinate provenance, and a location-specific historical baseline.
- Show location maps, charts, monthly anomalies, and downloadable observations.
- Pass the selected location's measurements into investigations. Never substitute
  Peru sample claims for another location. Clearly label statistical fallback
  while the Grok workflow remains unimplemented.
- Preserve Pacific NOAA indices and the 2017 Peru replay as optional specialist
  data, without implying they measure local ocean conditions everywhere.
- Country selection is a place-search filter; results represent the selected
  point/grid cell rather than a national average.
Implementation and teammate APIs: README.md and data/GLOBAL.md. Existing entry
signatures and shared schemas remain compatible.

ORIGINAL PROPOSAL (geographic scope superseded above)

READ FIRST: The repository skeleton already exists. Before writing code, read section 18 (Working in parallel without breaking each other) and README.md.

1. Define exactly what EarthWatch will do
The product in one sentence
EarthWatch is an AI-powered climate intelligence platform that detects unusual environmental conditions, investigates the evidence using multiple sources, and translates those findings into understandable regional risk assessments.

The target user is someone who needs to understand emerging environmental threats without manually analyzing multiple scientific datasets.

For the initial version, we'll focus on the eastern tropical Pacific and the potential implications of unusual ocean conditions for northern coastal Peru.
The user journey
Imagine a user opens EarthWatch and sees the following:

PACIFIC WATCH — INVESTIGATION REQUIRED
- Observed signal: Sea surface temperatures are unusually high relative to the historical baseline in a monitored ocean region.
- Statistical result: The anomaly detector identifies a deviation from the expected historical pattern.
- Climate investigation: The system examines whether additional oceanic and atmospheric indicators support the initial signal.
- Regional implications: The system investigates potential consequences for northern Peru, including rainfall and flooding concerns.
- Evidence status: Confirmed measurements, corroborating evidence, conflicting evidence, and unknowns are presented separately.
- Recommended next step: Review the latest official climate outlook and relevant regional hazard information.
These are illustrative results, not claims about current conditions. The live dashboard must populate them from actual data.

The user can then click Investigate to watch the agents examine the signal and assemble their assessment.

That last feature matters: judges should see the system doing real work, not simply displaying a prewritten AI response.
What we are NOT building
To keep the project feasible, the initial version will not:
- Train a new global climate model.
- Claim to predict El Niño from sea surface temperature alone.
- Forecast exact flood locations or casualties.
- Claim to provide official disaster warnings.
- Attempt to monitor every climate hazard around the world.
Instead, we will build a focused, reproducible climate-anomaly investigation system.

The central innovation is the connection between quantitative anomaly detection, autonomous evidence investigation, and regional impact analysis.
2. Divide the team into three workstreams
This is the most important organizational decision.

You have three people, so avoid assigning one person to each bot. That creates dependencies everywhere: each bot needs data, prompts, backend integration, and UI work.

Instead, assign ownership by technical specialty. Each person builds an independent component that can be tested on its own, and the three components integrate through a shared data contract.
Person 1 — Climate Intelligence Lead
Owns the scientific data, anomaly detection, and quantitative analysis.

This person is responsible for making sure EarthWatch is analyzing real environmental conditions rather than generating plausible-sounding climate claims.
Responsibilities
Task 1: Build the environmental data pipeline
- Retrieve historical and current sea surface temperature anomaly indices.
- Retrieve rainfall data for northern Peru.
- Normalize the measurements, dates, units, and geographic labels.
- Handle missing data and failed API requests.
- Record the source and observation date for every measurement.
Task 2: Implement anomaly detection

Start with a statistical baseline rather than a machine-learning model.

For a monthly measurement, calculate:
\[
A_t = X_t - \mu_m
\]
where:
- \(X_t\) is the observed measurement at time \(t\).
- \(\mu_m\) is the historical average for the corresponding calendar month.
- \(A_t\) is the anomaly relative to that month.
You can also calculate a standardized anomaly:
\[
Z_t = \frac{X_t-\mu_m}{\sigma_m}
\]
where \(\sigma_m\) is the historical standard deviation for that calendar month.

A large absolute \(Z_t\) indicates an unusual observation relative to the chosen historical baseline.

For example, an absolute standardized anomaly above 2 could be used as an initial investigation threshold. It is a heuristic, not a universal climate-warning threshold.

Important: If you use a source that already publishes anomalies calculated against a specified baseline, don't subtract the climatological mean again. Verify the data definition first.

Task 3: Build the historical replay
- Select a historical period with a meaningful climate signal.
- Retrieve the corresponding measurements.
- Calculate the anomaly series.
- Allow the application to step through the observations chronologically.
- Return the same output format as the live pipeline.
This is what will make the demonstration reliable.
Deliverables
1. A working data ingestion module.
2. A tested anomaly detection function.
3. A historical dataset for the demonstration.
4. A time-series chart or chart-ready dataset.
5. A documented data interface for the other teammates.
Definition of done
Person 1 is finished when another teammate can call a function and receive actual measurements, calculated anomalies, source metadata, and observation dates without needing to understand the underlying data retrieval code.
Suggested tools
- Python
- pandas and NumPy
- Plotly
- NOAA climate datasets
- Open-Meteo historical weather data
I'll specify the recommended data sources below.
Person 2 — Grok Agent Intelligence Lead
Owns the multi-agent system, evidence investigation, and reasoning workflow.

This person is responsible for the feature that distinguishes EarthWatch from a conventional climate dashboard.

The goal isn't to make four agents talk to each other. It's to create a workflow in which each agent contributes a distinct, verifiable piece of the investigation.
Responsibilities
Task 1: Design the agent architecture

Start with three logical agents and add a fourth only if time permits.
Agent	Input	Task	Output
Climate Investigator	Detected anomaly + source data	Investigate the signal and retrieve relevant evidence	Evidence report
Regional Impact Analyst	Verified observations + regional context	Assess potential implications for northern Peru	Impact assessment
Skeptic / Verifier	Draft assessment + underlying evidence	Find contradictions, unsupported claims, and uncertainty	Verification report
Briefing Agent	Final verified assessment	Create a concise, user-friendly summary	Climate briefing


The Briefing Agent can be a simple final processing step initially rather than a separate autonomous agent.

Task 2: Implement tool calling

The agents should be able to use controlled functions such as:
- get_climate_observations(region, start_date, end_date)
- get_rainfall_history(location, start_date, end_date)
- search_official_climate_sources(query)
- get_regional_context(location)
- calculate_anomaly(series, baseline)
The first two functions should retrieve actual data. The anomaly calculation should use your teammate's deterministic code.

You can expose these tools to Grok through function calling, rather than asking the model to estimate numerical values itself. The official xAI tool documentation describes how Grok can invoke custom functions and use web search to complete multi-step tasks. Grok API Documentation

Task 3: Build the investigation workflow

A successful workflow should look like this:
1. Receive a detected anomaly.
2. Retrieve the underlying measurements and their metadata.
3. Search official sources for relevant climate context.
4. Produce an initial hypothesis.
5. Ask the verifier to challenge that hypothesis.
6. Revise the assessment if the evidence warrants it.
7. Return a structured report to the frontend.
Don't let the investigator invent the observation or its numerical magnitude.

Task 4: Add evidence provenance

Every important factual claim should include:
- The claim.
- Its source.
- The date of the source or observation.
- Whether it is measured, reported, inferred, or uncertain.
- Any relevant limitations.
The verifier should flag claims without sufficient evidence rather than trying to manufacture a citation.
Deliverables
1. Working Grok API integration.
2. Agent prompts and tool definitions.
3. A functioning investigation workflow.
4. Structured JSON outputs.
5. Evidence verification and uncertainty handling.
6. A test investigation using the climate data supplied by Person 1.
Definition of done
Person 2 is finished when a detected anomaly can be passed into the system and it returns a structured, source-supported assessment that the frontend can display without parsing free-form prose.
Suggested tools
- Grok API
- Python
- Pydantic for structured output validation
- Official-source web search or controlled retrieval functions
- JSON for agent-to-agent communication
Critical rule: The LLM proposes interpretations; your code verifies data types, units, thresholds, timestamps, and other deterministic properties.
Person 3 — Product & Dashboard Lead
Owns the frontend, user experience, backend integration, and final demonstration.

This person is responsible for turning the scientific pipeline and agent workflow into a coherent product.

The UI should not look like a generic chatbot placed next to a graph. It should feel like a climate intelligence workstation.
Responsibilities
Task 1: Build the dashboard

Create four main sections:
1. Overview: Current monitoring status and the most important detected signals.
2. Climate Explorer: Time-series charts showing observations and anomalies.
3. Investigation: A timeline of what the agents are examining and what they found.
4. Regional Impact: A map or location-focused panel showing the selected region and relevant evidence.
Task 2: Build the anomaly detail view

When the user selects an anomaly, display:
- The variable and geographic region.
- The observed value and historical baseline.
- The anomaly magnitude and statistical method.
- The observation date and data source.
- The agent's investigation findings.
- Supporting and contradictory evidence.
- The assessment's confidence and limitations.
- Recommended next steps.
Task 3: Integrate the backend

Person 3 should establish the interface between the climate pipeline and the agent system early, not at the end.

For example, the dashboard should be able to call a single backend function:

investigate_anomaly(anomaly_id)

The backend retrieves the anomaly, invokes the agent workflow, validates the result, and returns a structured report.

The frontend should not need to know which agent performed each internal operation.

Task 4: Build the demo controls

Add controls that let judges:
- Select a region.
- Select a historical period.
- Trigger an investigation.
- Watch the investigation progress.
- Open the evidence supporting a finding.
- Compare the original observation with the agent's conclusions.
The most important control is Run Investigation. It should trigger actual backend processing.
Deliverables
1. Working dashboard.
2. Climate charts and anomaly cards.
3. Investigation progress and evidence views.
4. Integration with the two other workstreams.
5. A repeatable demonstration mode.
6. A polished final presentation.
Definition of done
Person 3 is finished when a judge can open the application, select an anomaly, trigger an investigation, inspect the resulting evidence, and understand the system's conclusion without needing to read the source code.
Suggested tools
- Streamlit for rapid development, or React if someone on the team is already comfortable with it.
- Plotly for charts.
- Folium or a suitable map component for geographic visualization.
- FastAPI if you want a separate backend.
- GitHub for version control.
My recommendation: Use Streamlit unless your team already has strong React experience. The objective is a polished, functioning product—not an unnecessarily complicated frontend architecture.
3. How the three workstreams connect
The team should agree on a common interface before anyone starts building independently.

Here is the proposed architecture:
                   ENVIRONMENTAL DATA
                           |
                           v
             PERSON 1: CLIMATE INTELLIGENCE
             - Retrieve observations
             - Calculate anomalies
             - Generate historical replay
                           |
                           v
                   DETECTED ANOMALY
                           |
                +----------+----------+
                |                     |
                v                     v
      PERSON 2: GROK AGENTS     PERSON 3: DASHBOARD
      - Investigate evidence    - Display observations
      - Analyze regional risk   - Render maps and charts
      - Challenge conclusions   - Manage user interactions
                |                     |
                v                     |
         VERIFIED REPORT              |
                |                     |
                +----------+----------+
                           |
                           v
                 EARTHWATCH INTERFACE
                           |
                           v
                USER EXPLORES EVIDENCE

In the final application, the frontend invokes the backend, and the backend calls the appropriate components. This diagram shows responsibilities rather than a literal execution sequence.
Establish the data contract immediately
Person 1 should produce anomaly records in a format like this:
{
  "anomaly_id": "pacific_sst_001",
  "variable": "sea_surface_temperature_anomaly",
  "region": "Nino 1+2",
  "observation_date": "2026-09-01",
  "value": 2.8,
  "unit": "degC",
  "baseline_period": "1991-2020",
  "source": "NOAA CPC",
  "detection_method": "published_anomaly_index",
  "status": "detected"
}

The numbers and dates above are illustrative only. The application must populate them from the selected dataset, not hardcode them.

Person 2 should return a report in a consistent format:
{
  "anomaly_id": "pacific_sst_001",
  "summary": "A positive sea-surface-temperature anomaly was detected.",
  "evidence": [],
  "supporting_findings": [],
  "contradictory_findings": [],
  "regional_implications": [],
  "confidence": "moderate",
  "limitations": [],
  "recommended_next_steps": []
}

The real report should contain source references, observation dates, and descriptions of the evidence behind each claim.

These contracts let Person 1 finish the data pipeline without waiting for the agent workflow, and let Person 3 build the interface with sample records before the live backend is ready.
4. Choose the right data sources
This decision can save you hours. Don't begin by downloading enormous satellite datasets or training a climate model. Start with datasets that are scientifically meaningful and easy to integrate.

I recommend using NOAA for oceanic climate indicators, Open-Meteo for historical rainfall, and NOAA's official climate outlook as an independent reference.
Source A: NOAA — Ocean temperature anomalies
Start with the NOAA Climate Prediction Center's climate indices. The page provides sea surface temperature indices for several equatorial Pacific regions, including Niño 1+2 and Niño 3.4. These indices are directly relevant to monitoring ENSO conditions. Climate Prediction Center

For EarthWatch, focus on two regions:
Index	Geographic focus	Why use it?
Niño 1+2	Far eastern tropical Pacific, near Peru and Ecuador	Relevant to local eastern-Pacific ocean conditions
Niño 3.4	Central-eastern equatorial Pacific	Commonly used to monitor broader ENSO conditions


The important distinction is that these indices measure different parts of the Pacific. A strong anomaly in one region does not necessarily imply the same magnitude or consequences in another.
Implementation
Person 1 should:
1. Locate a suitable downloadable NOAA time series.
2. Parse the observation dates and values.
3. Preserve the index definition and reference baseline.
4. Plot the index over time.
5. Identify observations that meet the project's anomaly-detection criteria.
For the MVP, using an already calculated NOAA anomaly index is preferable to calculating ocean-temperature anomalies from raw gridded data.
Optional enhancement
Use the NOAA Oceanic Niño Index information as an additional reference. The index is based on three-month running sea surface temperature anomalies in the Niño 3.4 region. It provides context for interpreting the larger ENSO pattern. Climate Prediction Center

Do not treat your custom anomaly detector as a replacement for NOAA's established ENSO classification.
Source B: Open-Meteo — Historical rainfall
Use the Open-Meteo Historical Weather API to retrieve historical precipitation data for locations in northern Peru. Its historical service provides reanalysis-based weather data, including precipitation, for dates extending back decades. Open Meteo

For your first implementation, select one or two locations in northern coastal Peru.

For example:
- Piura.
- Tumbes.
These locations provide a practical geographic focus for exploring rainfall variability.
Implementation
Person 1 should retrieve daily precipitation and calculate:
- Daily rainfall.
- Rolling seven-day precipitation totals.
- Monthly rainfall anomalies.
- Percentiles relative to a historical baseline.
A rainfall percentile can be particularly useful. If a seven-day accumulation is higher than 95% of comparable historical seven-day periods, it indicates an unusually wet period relative to that reference distribution.

However, make sure you compare like with like. Seasonal rainfall patterns matter, and a percentile calculated against all dates indiscriminately can be misleading.
Why this source is useful
You can retrieve real data without building a complex satellite-data processing pipeline.

Later, if time permits, you could investigate precipitation products from NASA's Global Precipitation Measurement mission, which provides satellite-derived precipitation estimates at multiple time resolutions. GPM

For the MVP, I would not make NASA data a dependency unless someone on your team already knows how to work with it.
Source C: NOAA — Official climate assessments
Use the NOAA Climate Prediction Center's ENSO Diagnostic Discussion as a reference for the broader climate context. NOAA publishes expert assessments that combine observations and multiple forecast models. Climate Prediction Center

The investigator should be able to answer:
- What does the official climate assessment say?
- Does it support the existence of the observed anomaly?
- What does it say about the broader ENSO state?
- Does it provide evidence about the regional consequences we're investigating?
- Which conclusions remain uncertain?
Importantly, NOAA's official outlook is a reference for verification, not a substitute for EarthWatch's own analysis.

Your system should compare its findings with the official assessment and disclose disagreements.
Recommended data strategy
Data	Primary source	Required for MVP?
Pacific sea surface temperature anomaly	NOAA	Yes
Historical rainfall in northern Peru	Open-Meteo	Yes
Official ENSO outlook	NOAA CPC	Yes
Satellite precipitation	NASA GPM	No
Live news or other reports	Official sources via search	Useful enhancement
Flood inundation maps	Appropriate geographic or satellite datasets	Optional


Don't integrate more data sources merely to increase the count. Two well-understood datasets and one authoritative reference are more valuable than six sources that you cannot interpret correctly.
5. Define the actual anomaly-detection logic
This is the scientific core of EarthWatch.

You need to decide what constitutes an anomaly, how to distinguish different types of signals, and how the system should react.

I recommend implementing two complementary detection methods.
Method A: Detect unusually warm ocean conditions
For the MVP, use the published NOAA ocean-temperature anomaly index as the input.

A simple threshold can flag a value for investigation, but distinguish your internal threshold from official ENSO criteria.

For example:
Condition	EarthWatch behavior
Small deviation from the reference	Continue monitoring
Unusual positive or negative deviation	Trigger an investigation
Persistent deviation across multiple observations	Raise the monitoring priority
Ocean signal plus unusual rainfall	Investigate a possible compound regional concern
Incomplete or conflicting data	Mark the assessment inconclusive


The threshold should be configurable and documented.

You can also calculate a rolling mean to distinguish persistent signals from isolated fluctuations.
Method B: Detect unusually high rainfall
For each selected location:
1. Retrieve historical daily precipitation.
2. Calculate seven-day rainfall accumulation.
3. Compare the accumulation with historical periods from the same season.
4. Calculate its historical percentile.
5. Flag unusual values for investigation.
For example, an observation in the 98th percentile of comparable historical rainfall periods could trigger a high-priority investigation.

That does not automatically mean a flood is occurring. It means the rainfall warrants further examination.
Method C: Combine signals without overstating causality
This is where EarthWatch can become more interesting than a basic monitoring dashboard.

Suppose the system detects:
- An unusually warm eastern Pacific.
- An unusually wet period in northern Peru.
- An official report discussing elevated regional climate risks.
EarthWatch could identify a compound signal requiring investigation.

It should not automatically conclude that the ocean anomaly caused the rainfall event.

To make that distinction explicit, separate three concepts:
1. Observation: What the data directly measures.
2. Association: Whether multiple indicators changed together.
3. Interpretation: What the combined evidence suggests and what remains unproven.
That distinction should appear in the UI and the agent output.
6. Design the multi-agent workflow
The four bots should function as an investigation pipeline, not a committee that produces four independent essays.
Bot 1: Ocean Sentinel
Purpose: Detect and characterize unusual environmental signals.

This bot should be grounded primarily in code, not free-form LLM reasoning.

It receives:
- A time series.
- Its source and units.
- Its historical baseline.
- The detection method.
It returns:
- The detected anomaly.
- Its magnitude.
- Its duration.
- The relevant observation dates.
- Whether additional investigation is warranted.
The quantitative calculations should happen in Python. Grok can help interpret the results, but it should not be allowed to invent the underlying measurements.
Bot 2: Climate Investigator
Purpose: Establish what the available evidence actually supports.

It receives the anomaly record and uses approved tools to investigate it.

It should:
1. Read the original measurements.
2. Check the data source and dates.
3. Retrieve the relevant official climate outlook.
4. Find independent supporting or contradictory evidence.
5. Explain the difference between an observation and an inference.
Its output is a structured evidence report.
Bot 3: Regional Impact Analyst
Purpose: Translate the climate evidence into a geographically specific assessment.

For the MVP, constrain the scope to Piura and Tumbes.

It should investigate:
- Whether the observed climate signal has a documented relationship with regional rainfall.
- Whether rainfall observations are themselves unusual.
- Which official regional hazard information is relevant.
- Which locations or sectors might warrant further monitoring.
Avoid asking this agent to generate precise flood probabilities unless you have a validated model and suitable data.

Instead, let it identify potential concerns, supporting evidence, and unresolved questions.
Bot 4: Skeptic / Verifier
Purpose: Challenge the other agents' conclusions.

This agent receives the draft assessment and checks for:
- Unsupported causal claims.
- Incorrect or mismatched dates.
- Contradictory sources.
- Confusion between observation and forecast.
- Missing evidence.
- Overconfident recommendations.
- Claims that extend beyond the geographic coverage of the data.
Its response should identify each issue and explain what needs to be corrected.

If the evidence is insufficient, it should be able to reject the assessment or downgrade its confidence.
What about the Briefing Bot?
You can initially implement the final briefing as a structured transformation of the verified assessment. You don't need a fifth independent agent.

This keeps the architecture manageable.
The workflow in practice
1. DETECT
   Statistical code identifies an unusual observation.

2. INVESTIGATE
   Grok searches approved sources and examines the evidence.

3. ASSESS
   The Regional Impact Analyst investigates possible implications.

4. CHALLENGE
   The Skeptic checks the evidence and challenges unsupported claims.

5. REVISE
   The system corrects, qualifies, or rejects the initial assessment.

6. PRESENT
   The dashboard displays the final report with evidence and uncertainty.

If the Skeptic identifies a substantive error, allow one revision cycle. Repeatedly asking agents to reconsider their conclusions can waste time and API budget without improving the result.
Implemented agent workflow (agents/workflow.py, Person 2)
The four bots are implemented as follows. The Skeptic / Verifier sits between the Impact Bot and the Action Bot so that the Action Bot only works from verified findings.
1. Sentinel Bot (code, no LLM): re-checks the detected signal against source data, reports whether the record's value reproduces (confirmed / mismatch / unverified) and how persistent it is.
2. Investigator Bot: researches the signal with data tools and must test at least two alternative explanations (natural variability, data artifact, another climate mode), marking each supported, unsupported or untested.
3. Impact Bot: estimates, qualitatively, who or what could be affected. Every exposure needs a basis and an uncertainty; no counts, probabilities or casualty estimates.
4. Skeptic / Verifier and Reviser: challenge the draft; one revision cycle at most.
5. Action Bot: turns the verified findings into an alert, a short report and a contingency plan (Assessment.action_plan). It has no data tools and cannot add facts.
Code enforces the limits: the alert level can never exceed what the confidence, the record's status and the Sentinel check justify; causal or certainty language is marked [Unverified]; if the Action Bot fails, the rest of the assessment is still returned and the gap is disclosed. Person 3: render assessment.action_plan (alert_level, alert_headline, alert_message, report, contingency_plan, monitoring_triggers, level_reason, disclaimer) on the Regional Impact screen; sample_data/assessment.json contains an example.
7. Build the dashboard around an investigation
Your interface should make the project feel like a real product.

I recommend a dark, satellite-inspired visual style with a geographic map, clear anomaly indicators, and a central investigation panel. But don't sacrifice readability for aesthetics.
Screen 1: EarthWatch Overview
The first screen should answer three questions immediately:
1. What is happening?
2. Where is it happening?
3. Why should I care?
Suggested layout:
+---------------------------------------------------------------+
| EARTHWATCH                         PACIFIC CLIMATE INTELLIGENCE |
+---------------------------------------------------------------+
|                                                               |
|  MONITORING STATUS                                            |
|  Pacific SST       [Signal detected / Normal / Data unavailable]|
|  Northern Peru     [Rainfall status]                           |
|  Official outlook  [Latest published assessment]               |
|                                                               |
+----------------------------------+----------------------------+
|                                  |                            |
|       INTERACTIVE MAP            |   ACTIVE INVESTIGATIONS    |
|                                  |                            |
|  Eastern Pacific                 |   01  Ocean anomaly        |
|  Northern Peru                   |   02  Rainfall deviation    |
|  Selected monitoring locations  |   03  Evidence review      |
|                                  |                            |
+----------------------------------+----------------------------+
|                                                               |
|              [ RUN CLIMATE INVESTIGATION ]                    |
|                                                               |
+---------------------------------------------------------------+

These are layout suggestions, not actual live measurements.

Use a visible source timestamp so the judge can distinguish current observations from older or cached data.
Screen 2: Climate Explorer
This screen is for users who want to examine the underlying measurements.

Include:
- A sea surface temperature anomaly time series.
- A historical baseline or reference threshold.
- A rainfall time series for the selected location.
- A historical replay control.
- Source and observation metadata.
When the user selects a point on a chart, show the exact value, unit, date, and source.

Don't overload the page with charts. Two well-designed charts that explain the investigation are enough.
Screen 3: Investigation Center
This should be the most distinctive screen.

When the user clicks Run Investigation, show a timeline:
09:41:02  Ocean Sentinel
          Unusual observation identified.
          Statistical result available.

09:41:04  Climate Investigator
          Checking official climate context.

09:41:08  Regional Impact Analyst
          Examining rainfall observations in Piura.

09:41:12  Skeptic / Verifier
          Reviewing the draft for unsupported conclusions.

09:41:15  Assessment completed
          Evidence report ready.

The timestamps and findings above are illustrative.

The application must display actual progress events from the backend. Don't fake a live multi-agent investigation with a hardcoded animation.

For each step, let the user expand:
- The agent's task.
- The source it consulted.
- Its finding.
- Any unresolved questions.
This provides a visible demonstration of agent collaboration.
Screen 4: Regional Impact Briefing
The final screen should contain:

Headline: A concise description of the observed signal.

What we observed: Measured facts with dates and units.

Why it matters: The potential implications, clearly distinguished from confirmed outcomes.

Evidence: Sources supporting or contradicting the assessment.

Confidence: A qualitative assessment based on evidence completeness and agreement, with an explanation.

Recommended monitoring actions: What a user should check next, including relevant official sources.

Limitations: What the system cannot conclude.

A good interface should make it easy to inspect the evidence without overwhelming the user with technical detail.
8. Set the scope: MVP versus stretch goals
One of the biggest hackathon risks is trying to implement every interesting feature at once.

I would use three levels of scope.
Tier 1 — Must work
These are the features you should finish before adding anything else.
Feature	Owner
Real NOAA ocean-temperature anomaly data	Person 1
Real historical rainfall data	Person 1
At least one working statistical anomaly detector	Person 1
Grok-powered evidence investigation	Person 2
A verifier that challenges unsupported claims	Person 2
Structured assessment with sources and limitations	Person 2
Dashboard with charts and anomaly cards	Person 3
A working Run Investigation button	Person 3
Historical replay or reproducible investigation	Shared
End-to-end testing	Shared


Definition of a successful MVP: A judge selects an anomaly, the system retrieves the underlying data, the agents investigate it, and the dashboard displays an evidence-supported assessment.

If all of these work, you have a complete product.
Tier 2 — Add if time permits
- Interactive geographic map.
- Multiple monitoring locations.
- Historical playback animation.
- Source comparison view.
- Agent disagreement visualization.
- Exportable climate briefing.
- Live retrieval of additional official reports.
These improve the user experience and demonstration but shouldn't block the core pipeline.
Tier 3 — Only if the core is finished
- A more advanced forecasting model.
- Multiple climate hazards.
- Automated periodic monitoring.
- Notifications when new anomalies appear.
- A user-defined monitoring region.
- More sophisticated geographic exposure analysis.
- More extensive satellite data integration.
I would not prioritize machine-learning forecasting over a reliable, well-tested anomaly investigation system.
9. Execution schedule: How to work in parallel
Since you haven't specified the hackathon duration, here's a plan for a 24-hour competition. If you have a different duration, preserve the order and adjust the time allocations.

The biggest efficiency gain comes from agreeing on the data contract during the first hour.
Phase 1 — Alignment and setup
Hour 0–1
Everyone together

Agree on:
- The exact problem statement.
- The geographic focus.
- The first two data sources.
- The shared anomaly and assessment schemas.
- The technology stack.
- The minimum demo scenario.
Create a shared repository and a minimal application skeleton.

Assign one person responsibility for integration and deployment. I recommend Person 3 because that person owns the application, but deployment must not become an afterthought.

Deliverable: Everyone knows what they are building, how it connects, and what constitutes completion.
Phase 2 — Build the independent components
Hours 1–5
Person	Primary task	Required output
Person 1	Data retrieval and anomaly detection	Real anomaly records and chart-ready data
Person 2	Grok integration and investigation workflow	Structured assessment from a sample anomaly
Person 3	Dashboard skeleton and visual design	Working UI with sample records


Everyone should use mock data wherever another component is not ready.

For example, Person 2 can build and test the investigator using a sample anomaly JSON record. Person 3 can build the dashboard using the same record.

Do not wait for all three components to be complete before testing integration.
Phase 3 — First integration
Hours 5–9
Bring the three workstreams together.

Person 1 connects the actual data pipeline to the shared schema.

Person 2 replaces the sample anomaly with the actual input and verifies that the agent workflow can process it.

Person 3 connects the Run Investigation button to the backend and displays the returned assessment.

By the end of this phase, you should have one complete investigation working from data retrieval through to the interface.

If a feature blocks this integration, simplify it.

For example, if a geographic map takes too long to implement, use a location selector and a well-designed regional panel.
Phase 4 — Make the investigation credible
Hours 9–14
Person 1
- Validate the anomaly calculations.
- Check units, dates, baseline definitions, and missing observations.
- Test a historical period with a meaningful signal.
- Ensure the results are reproducible.
Person 2
- Improve source attribution.
- Add the Skeptic / Verifier.
- Validate the structured output.
- Test contradictory or insufficient evidence.
- Ensure the agent does not claim a causal relationship without support.
Person 3
- Improve the charts and investigation timeline.
- Add evidence details and source links.
- Improve loading, error, and data-unavailable states.
- Make the interface understandable without a verbal explanation.
Shared milestone: The product works end to end and produces a defensible result.
Phase 5 — Improve the demo
Hours 14–19
Focus on the features that make the project memorable.

I would prioritize:
1. Historical replay.
2. Visible agent investigation.
3. Clickable evidence.
4. A clear regional assessment.
5. A polished overview screen.
Run the complete demonstration several times.

If live data retrieval is slow or unreliable, cache the underlying historical observations while still executing the anomaly analysis and investigation workflow during the demo.

Be transparent when using cached observations.
Phase 6 — Testing and final polish
Hours 19–22
Test the following scenarios:
- A strong positive anomaly.
- A normal or unremarkable observation.
- A negative anomaly.
- Missing or incomplete data.
- Conflicting evidence.
- A failed external API request.
- An agent returning invalid structured output.
- An investigation that concludes there is insufficient evidence.
You don't need to build an elaborate interface for every scenario. But the application should fail gracefully instead of crashing or inventing results.
Phase 7 — Rehearse and present
Hours 22–24
Reserve the final two hours for:
- Rehearsing the presentation.
- Checking the deployment.
- Verifying API credentials and quotas.
- Testing the exact demonstration sequence.
- Preparing a fallback if a live source fails.
- Assigning speaking roles.
Do not spend the final hour adding an entirely new feature.
If your hackathon is shorter
For a 12-hour hackathon, aim for:
- Hours 0–1: Scope and contracts.
- Hours 1–4: Parallel implementation.
- Hours 4–7: End-to-end integration.
- Hours 7–9: Verification and UI polish.
- Hours 9–12: Testing, deployment, and presentation.
For a weekend competition, use the 24-hour plan for the first day and spend the remaining time improving reliability, originality, and evaluation.
10. How to demonstrate that EarthWatch actually works
A strong hackathon project needs more than an impressive-looking interface. You should be able to show that the system produces useful results and handles uncertainty responsibly.

I recommend preparing one primary demonstration and two smaller verification tests.
Primary demonstration: Replay a historical climate event
Choose a historical period with a documented Pacific climate anomaly.

The demonstration should proceed chronologically:
1. The user opens EarthWatch.
2. The system displays historical observations leading up to the selected event.
3. The anomaly detector identifies an unusual measurement.
4. The user clicks Investigate.
5. The Climate Investigator retrieves relevant official climate context.
6. The Regional Impact Analyst examines the rainfall data.
7. The Skeptic checks the resulting assessment.
8. EarthWatch displays the final evidence-based briefing.
The key is to show the sequence of discovery.

Do not simply show a large anomaly that is already obvious. Show how the system identifies the signal, gathers supporting evidence, and determines what can reasonably be concluded.
How to avoid hindsight bias
When replaying a historical event, preserve the dates on which information became available.

For example, if you are replaying a period from several years ago, the agent should not use a climate report published months after the event as though that information had been available at the beginning.

You can use later publications to validate the outcome, but label them as retrospective evidence.

This is a small detail that could distinguish your project from a superficial climate demo.
Verification test 1: The Skeptic catches an unsupported claim
Provide the system with an anomaly that is real but insufficient to support a strong regional conclusion.

The Investigator might propose that the anomaly could be associated with elevated rainfall risk.

The Skeptic should recognize that the evidence does not establish that the specific location will experience flooding.

The final assessment should qualify the claim and explain what additional evidence is required.

This demonstrates that your multi-agent system is not simply designed to agree with itself.
Verification test 2: The system handles missing data
Remove one of the supporting data sources or simulate an API failure.

EarthWatch should identify which evidence is missing and lower the completeness of its assessment.

It should not fabricate rainfall observations or pretend that it successfully checked a source.

A system that knows when it cannot reach a conclusion is more credible than one that always returns a confident answer.
11. How to measure success
Even in a short hackathon, define a few measurable acceptance criteria.

These are engineering targets for your prototype, not claims of scientific accuracy.
Component	Acceptance criterion
Data pipeline	Successfully retrieves and parses the selected environmental observations
Anomaly detector	Reproduces the expected result for known test cases
Historical replay	Produces consistent results for the same dataset and configuration
Agent workflow	Completes an investigation using the provided anomaly record
Evidence handling	Every important factual claim in the final report has traceable supporting evidence or is explicitly marked unsupported
Skeptic	Identifies at least one deliberately introduced unsupported claim in a controlled test
Frontend	A judge can trigger an investigation and inspect the resulting evidence
Reliability	Missing data and API failures produce informative error states
Demonstration	The complete demo succeeds in repeated rehearsals


For anomaly detection, create a small set of test cases with known expected results.

For example:
- A series of normal observations.
- A series with one extreme outlier.
- A series with a persistent deviation.
- A series with missing measurements.
This allows Person 1 to validate the calculations independently of the LLM.

For the agent workflow, create several test reports containing deliberately introduced errors. Check whether the verifier identifies the errors instead of merely returning a generic statement that the analysis looks reasonable.

You do not need hundreds of tests. A small, thoughtfully designed test suite is much better than relying on the agents' outputs looking convincing.
12. Prepare for the judging criteria
Your competition scores Idea, User Experience, and Implementation most heavily, with Demo weighted less. Therefore, the project should prioritize actual functionality and a polished user experience over a theatrical presentation.
Idea: Make the product more than a climate dashboard
The differentiation is the autonomous investigation of an environmental signal.

A conventional dashboard might display an ocean-temperature anomaly.

EarthWatch should answer:
- Is the measurement unusual relative to an appropriate baseline?
- Does additional evidence support the signal?
- What is known about its possible regional implications?
- What evidence is missing?
- What should a user investigate next?
Your novelty claim should be specific. Don't claim that nobody has ever built climate anomaly detection or climate intelligence software.

Instead, emphasize your implementation: a focused, evidence-traceable, multi-agent workflow that connects oceanic signals, regional rainfall observations, and uncertainty-aware assessments.
User experience: Make the result understandable in 30 seconds
A judge should not need to understand ENSO, anomaly statistics, or multi-agent architecture to appreciate the product.

The overview should explain the detected signal in plain language, while the detailed view provides the technical evidence.

Use clear labels:
- Observed.
- Investigating.
- Supported.
- Conflicting.
- Inconclusive.
Avoid presenting an arbitrary AI confidence score as if it were a calibrated probability of a climate event.
Implementation: Demonstrate genuine technical work
The strongest technical story has three parts:

1. Deterministic scientific computation

Your team retrieves real data and calculates or validates environmental anomalies.

2. Autonomous evidence investigation

Grok uses tools to gather evidence, examine the anomaly, and construct a structured assessment.

3. Adversarial verification

A separate verification step challenges unsupported claims and ensures that the final result reflects the available evidence.

The integration is the product. The number of agents is not.
Demo: Show a discovery, not a slideshow
The presentation should revolve around one question:

Can EarthWatch turn an unusual climate measurement into a more useful, evidence-based regional assessment?

Demonstrate the answer rather than spending several minutes describing the architecture before showing the application.
13. The biggest risks and how to avoid them
Risk	Why it matters	Mitigation
Scope creep	Too many datasets and features prevent completion	Focus on one ocean region and two regional rainfall locations
API complexity	Scientific datasets may require substantial preprocessing	Start with published NOAA indices and Open-Meteo
Slow agent execution	Multiple agents can increase latency and cost	Use a sequential workflow with a limited number of calls
Hallucinated evidence	An agent may invent a source or misrepresent a finding	Require traceable sources and validate claims against retrieved content
False causal claims	Correlated climate signals do not prove a specific cause	Separate observations, associations, and interpretations
Misleading anomaly scores	An arbitrary threshold can look like an official warning	Document the detection method and distinguish it from official criteria
Fake agent activity	Simulated logs undermine the product's credibility	Display real backend progress events
Live-demo failure	External services may be slow or unavailable	Cache historical data and prepare a reproducible scenario
Overcomplicated frontend	Styling consumes time needed for integration	Build the working investigation first, then polish
No evaluation	You cannot demonstrate whether the system performs as intended	Prepare known test cases and controlled verification tests


One additional risk is especially important: don't confuse a climate anomaly with a disaster forecast.

EarthWatch can identify unusual conditions and investigate potential consequences. It cannot reliably predict a specific flood, its severity, or its exact location merely by detecting an ocean-temperature anomaly.

That limitation should be visible in the final assessment, not buried in the technical documentation.
14. Recommended technical stack
Keep the architecture simple enough for three people to build quickly.
Layer	Recommendation	Purpose
Programming language	Python	Shared language across the project
Scientific data	pandas, NumPy	Data cleaning and anomaly calculations
Climate data	NOAA + Open-Meteo	Environmental observations
Agent intelligence	Grok API	Evidence investigation and assessment
Structured outputs	Pydantic	Validate agent responses
Backend	FastAPI or direct Python functions	Connect data, agents, and frontend
Frontend	Streamlit	Rapidly build the interactive dashboard
Charts	Plotly	Interactive climate time series
Maps	Folium or a Streamlit-compatible mapping component	Geographic context
Version control	GitHub	Collaboration and integration
Deployment	A platform that supports Python applications and secrets	Share the working prototype


The Grok API documentation describes the available tool-calling architecture. Before implementation, confirm that your hackathon credentials support the specific tools you intend to use. Grok API Documentation
Architecture recommendation
For a 24-hour hackathon, I would use:

Streamlit + Python + pandas + Plotly + Grok API.

You can build the backend as ordinary Python modules first and add FastAPI only if you need a separate service.

The actual repository structure (already created; owner in brackets):
ACM x TESC Hackathon/
│
├── app.py                      [P3] Streamlit entry point; calls translator.py only
├── translator.py               [P3] Only bridge between dashboard and backend
├── config.py                   [P3] Reads .env; the only place secrets are loaded
│
├── data/                       [P1]
│   ├── climate_sources.py      get_sst_series(region) -> DataFrame(date, value)
│   ├── rainfall_sources.py
│   └── cache.py
│
├── analysis/                   [P1]
│   ├── anomaly_detection.py    detect_anomalies() -> list[AnomalyRecord]
│   ├── rainfall_analysis.py
│   └── validation.py
│
├── agents/                     [P2]
│   ├── workflow.py             run_investigation(anomaly, on_progress) -> Assessment
│   ├── investigator.py
│   ├── regional_impact.py
│   ├── skeptic.py
│   └── briefing.py
│
├── dashboard/                  [P3]
│   ├── charts.py
│   ├── maps.py
│   └── components.py
│
├── schemas/                    [TEAM] Shared contracts; change only by agreement
│   ├── anomaly.py              AnomalyRecord, SERIES_COLUMNS
│   ├── assessment.py           Assessment, EvidenceItem, ProgressEvent
│   └── errors.py               TranslatorError
│
├── sample_data/                [TEAM] Labelled fake data used until stubs are built
│   ├── anomalies.json
│   ├── assessment.json
│   └── sst_series.csv
│
├── tests/
│   ├── conftest.py             [P3] stubbed_backend fixture
│   ├── test_contracts.py       [TEAM] sample data must match schemas
│   ├── test_translator.py      [P3]
│   ├── test_app.py             [P3] app renders and investigates without crashing
│   ├── test_anomalies.py       [P1]
│   └── test_agents.py          [P2]
│
├── .github/
│   ├── workflows/tests.yml     CI: runs pytest on every push and pull request
│   └── pull_request_template.md
│
├── requirements.txt            [TEAM]
├── pytest.ini
├── .env.example
└── README.md

Person 1 owns data/ and analysis/. Person 2 owns agents/. Person 3 owns app.py, translator.py, config.py and dashboard/, coordinating integration with both teammates. schemas/, sample_data/ and requirements.txt belong to the whole team.

Keep API keys in environment variables or your deployment platform's secrets manager. Never commit them to GitHub.
15. Your first 60 minutes: Exactly what to do
Here's how I would start the competition.
Minutes 0–15: Agree on the product
As a team, write down:
- User: Someone who needs to understand emerging environmental risks.
- Geographic focus: Eastern tropical Pacific and northern coastal Peru.
- Core capability: Detect an anomaly, investigate the evidence, and produce a regional assessment.
- Demo scenario: A historical Pacific climate event.
- Minimum success condition: A complete investigation using real observations and an actual Grok-powered workflow.
Minutes 15–30: Set up the repository and interfaces
The repository and application skeleton already exist. Everyone clones it, follows the README setup, runs `streamlit run app.py` and `pytest`, and creates their own branch (section 18).

All three review schemas/anomaly.py and schemas/assessment.py together and agree on any changes now. This is the cheapest moment to change the contract.

Person 1 selects the first NOAA dataset and verifies that it can be retrieved and parsed.

Person 2 verifies Grok API access and creates a minimal test that returns structured JSON.
Minutes 30–60: Begin independent implementation
Person 1: Retrieve the ocean-temperature index, calculate or validate anomalies, and create the first chart.

Person 2: Implement the Investigator using a sample anomaly record and return a structured report with source references.

Person 3: Build the dashboard with sample anomaly cards, a chart, and an investigation panel.

At minute 60, everyone should have something tangible to show.

If someone is blocked, they should continue using the shared sample data rather than waiting for another teammate.
16. The final presentation
Aim for a concise presentation that emphasizes the product's value and shows the system working.

Here's a suggested three-minute demo.
0:00–0:25 — Introduce the problem
Explain that environmental data is abundant, but detecting an unusual measurement is only the beginning. Users also need to understand what the signal means, whether other evidence supports it, and what remains uncertain.
0:25–0:50 — Introduce EarthWatch
Show the dashboard.

Explain that EarthWatch combines statistical anomaly detection, Grok-powered evidence investigation, and regional climate analysis.
0:50–1:30 — Demonstrate the detection
Select a historical observation and show the actual data, baseline, and anomaly calculation.

Explain how the system identified the signal.
1:30–2:15 — Demonstrate the agents
Trigger the investigation.

Show the Investigator examining the official climate context, the Regional Impact Analyst checking the selected locations, and the Skeptic challenging an unsupported conclusion.

This is the central moment of the presentation.
2:15–2:40 — Show the final assessment
Display the findings, supporting evidence, contradictions, limitations, and recommended next steps.

Emphasize that the system distinguishes observations from hypotheses.
2:40–3:00 — Close with the value
Explain that EarthWatch is designed to reduce the effort required to move from scattered environmental signals to a traceable, understandable climate assessment.
17. Final team checklist
Before submitting, verify that each item is complete.
Person 1 — Climate Intelligence
- [ ] Real NOAA ocean-temperature anomaly data.
- [ ] Historical rainfall data for selected locations.
- [ ] Validated anomaly calculations.
- [ ] Historical replay dataset.
- [ ] Source, unit, and timestamp metadata.
- [ ] Tests for normal, extreme, and missing observations.
Person 2 — Grok Agent Intelligence
- [ ] Working Grok API integration.
- [ ] Investigator retrieves and evaluates relevant evidence.
- [ ] Regional Impact Analyst produces a qualified assessment.
- [ ] Skeptic challenges unsupported conclusions.
- [ ] Structured and validated JSON outputs.
- [ ] Sources and limitations included in the final assessment.
- [ ] At least one controlled test of a deliberately unsupported claim.
Person 3 — Product Engineering
- [ ] Working dashboard.
- [ ] Climate anomaly charts.
- [ ] Investigation trigger and actual backend integration.
- [ ] Visible investigation progress.
- [ ] Evidence and regional assessment views.
- [ ] Informative error states.
- [ ] Repeatable demonstration mode.
- [ ] Successful deployment and final rehearsal.
Everyone
- [ ] End-to-end investigation works.
- [ ] Historical demo is scientifically defensible.
- [ ] No invented measurements or citations.
- [ ] Missing evidence is clearly identified.
- [ ] API keys are secured.
- [ ] CI (pytest) is green on main and no SAMPLE DATA banners appear in the demo.
- [ ] The product is demonstrably more than a chatbot.
- [ ] Each team member can explain their contribution.
My final recommendation
The strongest version of EarthWatch is not the one with the most agents, the most elaborate map, or the most ambitious forecasting claims.

It's the one that takes a real environmental signal, investigates it autonomously, challenges its own conclusions, and produces a useful assessment with evidence that a human can inspect.

That is the capability your team should optimize for.

If you execute the core workflow well, you will have three things judges can evaluate directly: a working scientific data pipeline, a meaningful application of Grok-powered agents, and an intuitive product that communicates its findings clearly.

One final question that would materially change this plan: how long is your SpaceX hackathon, and are you required to use the actual Grok Bots product, or can you build with the Grok API? Those two details determine how much agent orchestration to attempt and which features should be prioritized.

18. Working in parallel without breaking each other
Three people pushing at different times is normal. Git only conflicts when two people change the same lines of the same file, and the app only crashes at integration when someone breaks the shared contract. The repository is set up so neither should happen if everyone follows these rules.
Rule 1 — Only edit files you own
Owner	Files you may edit freely
Person 1	data/, analysis/, tests/test_anomalies.py
Person 2	agents/, tests/test_agents.py
Person 3	app.py, translator.py, config.py, dashboard/, tests/conftest.py, tests/test_translator.py, tests/test_app.py
Whole team	schemas/, sample_data/, requirements.txt, tests/test_contracts.py, plan.md, README.md

Every file starts with an "Owner:" line. If you need a change in someone else's file, ask them to make it. You can add new files inside your own folders at any time; new files never conflict.
Rule 2 — Shared files change only by agreement
For schemas/, sample_data/ or requirements.txt:
1. Announce the change in the team chat and wait for a thumbs-up.
2. One person makes the change. If a schema changes, update sample_data/ in the same commit.
3. Run pytest, push, and tell the team.
4. Everyone runs git pull --rebase origin main right away.
For requirements.txt, add one library per line. If it conflicts, keep both sides' lines.
Rule 3 — Never change the entry functions' names or signatures
The app reaches each workstream through exactly one function:
- Person 1: analysis/anomaly_detection.py → detect_anomalies() -> list[AnomalyRecord]
- Person 1: data/climate_sources.py → get_sst_series(region) -> DataFrame with columns date, value
- Person 2: agents/workflow.py → run_investigation(anomaly, on_progress) -> Assessment
While a function still raises NotImplementedError, translator.py automatically uses sample_data/ and the dashboard shows a SAMPLE DATA banner. When you implement your function, your banner disappears with no change to anyone else's code.

If your function cannot produce a real result (API down, missing data), raise an exception. Never return invented values. translator.py turns the exception into a readable error in the UI instead of a crash.

Person 2: call on_progress(ProgressEvent(...)) at each real agent step so the Investigation timeline shows genuine progress.
Rule 4 — Git workflow
Each person works on their own branch and merges small, working pieces into main often.

git checkout main
git pull --rebase origin main
git checkout -b p1-climate        # p2-agents / p3-dashboard

# ...work...
git add <your files>
git commit -m "Short description"
git pull --rebase origin main     # pick up teammates' work before every push
pytest                            # must pass
git push origin p1-climate
# open a pull request into main; merge when CI is green

- Commit small and often, at least every hour.
- Pull from main at least every 1–2 hours so you never drift far behind.
- Never force-push to main. Never commit .env or API keys.
- Use git add <your files> rather than git add . so you don't accidentally commit someone else's half-finished work or secrets.
Rule 5 — Keep CI green
.github/workflows/tests.yml runs pytest on every push and pull request. Don't merge a red pull request. The tests already check:
- Sample data matches the shared schemas (catches someone changing a schema alone).
- The translator rejects bad ids, unknown regions, malformed backend output and crashes, converting them into TranslatorError.
- The Streamlit app renders and runs an investigation without throwing, even when a backend function crashes.
Person 1 and Person 2 add their own tests to their own test files.
If you do hit a merge conflict
1. Don't panic, and don't delete the other person's work.
2. Open the file and find the <<<<<<<, =======, >>>>>>> markers.
3. Keep both sides' intent, remove the markers, and run pytest.
4. git add <file>, then git rebase --continue.
5. If the file isn't yours, ask its owner to resolve it with you.
What the setup prevents
Mechanism	Prevents
One owner per folder	Two people editing the same lines
Shared schemas + contract tests	Silent contract changes that crash integration
translator.py as the only bridge	The UI depending on backend internals
Sample-data fallback	Being blocked waiting for a teammate
TranslatorError + error states in the UI	Stack traces during the demo
.gitattributes line-ending rules	Whole-file diffs between Windows and macOS
.env.example + .gitignore	Leaked API keys
CI on every push	Broken code reaching main

Integration order
1. Person 1 implements detect_anomalies() and get_sst_series(). The Anomalies and Observations banners disappear.
2. Person 2 implements run_investigation(). The Assessment banner disappears.
3. Person 3 polishes the UI throughout, using sample data until real data arrives.
4. Demo-ready means no SAMPLE DATA banners and CI green on main.
