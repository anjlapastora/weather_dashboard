# Helios — Session Prompts

All user prompts from the Helios weather dashboard development session.


## Prompt 1
*2026-06-29 09:22 UTC*

Hourly Time Series is not showing data

---

## Prompt 2
*2026-06-29 09:51 UTC*

in the date range, limit only the dates to 30 days

---

## Prompt 3
*2026-06-29 09:56 UTC*

Can i also inject an automated test here?

---

## Prompt 4
*2026-06-29 10:18 UTC*

Help me create my own Chatbot and embed it here. use the following tech stack:
FastAPI · LangChain · ChromaDB · Ollama · sentence-transformers · Pydantic v2

create unit tests and update the readme also on how to use or operate the chatbot.

---

## Prompt 5
*2026-06-30 02:58 UTC*

Add supporting documents from the following questions:
"Which site had the highest average solar radiation last week?"
"Were there any anomalous wind speed readings at Site B in the last 7 days?"
"Compare generation potential across all three sites for the past month."
Check the data from the database to create supporting answers.

Whenever a user is typing or saying "Site A" or B or C, ask then which site they are referring to.

---

## Prompt 6
*2026-06-30 03:23 UTC*

Add favicon to the html file. i added the favicon folder already.

---

## Prompt 7
*2026-06-30 03:45 UTC*

check the entire repository if there are access keys being passed. or api keys

---

## Prompt 8
*2026-06-30 03:54 UTC*

Check the helios-backend folder. analyze if the pulling of data from the API is manual or scheduled. if the pulling is manual, create a celery scheduler to schedule the pulling of data every 00:00 of the day.

---

## Prompt 9
*2026-06-30 04:09 UTC*

after adding the scheduler, update the readme about the scheduler and add tests.

---

## Prompt 10
*2026-06-30 04:15 UTC*

Check the documents. seems like the dates added are not dynamic. make it dynamic so that when questions like "Were there any anomalous wind speed readings at Site B in the last 7 days?", it will check the date from 7 days until the date the query was sent.

---

## Prompt 11
*2026-06-30 04:50 UTC*

refine the answers. it seems like computations are based on z-score, but i chose IQR. make the computations all based on IQR only.

---

## Prompt 12
*2026-06-30 05:17 UTC*

im trying to add "notes for future use" . i also wanted to add a note to run another scheduler server to pull the data from the API every 00:00. Can you help me add that note to README?

---

## Prompt 13
*2026-06-30 05:20 UTC*

Add like a guide for first-time visitor of the website, like a walkthrough of the website.

---

## Prompt 14
*2026-06-30 05:25 UTC*

do the same thing on the html file. make it like a step-by-step walkthrough

---

## Prompt 15
*2026-06-30 05:45 UTC*

can you help me refine the dashboard again?. make sure that whenever i change the primary variable, change also the KPI cards and anomaly log

---

## Prompt 16
*2026-06-30 05:55 UTC*

this html file is too long. create a new folder called helios-frontend and split the helios_dashboard by html, style and js. location of the helios-frontend should be at the same location as helios-backend

---
