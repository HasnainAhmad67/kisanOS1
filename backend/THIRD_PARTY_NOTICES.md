# Third-party and team-code notices

The `app/team_agents/weather`, `app/team_agents/water`, and `app/team_agents/vision` directories contain source files copied from the three KisanOS teammate ZIP archives supplied for this task. They are included for attribution, integration and review. No license file was present in those archives. Confirm authorship and obtain an explicit license from the contributors before redistributing or deploying this package outside the team. Do not infer a permissive/open-source license from the PRD's open-source-first goal.

Python dependencies are declared in `requirements.txt`; their respective upstream licenses remain those of their authors. The original agent dependencies and APIs are not all enabled in the backend runtime. Gemini/Groq agent integrations remain disabled for farmer photos under the PRD's privacy boundary.
