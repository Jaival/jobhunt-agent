# Job sources: read by the daily routine

Edit this file to add or remove platforms or change search terms. No need to touch the routine itself.
Claude updates the "Status" column after each run (ok / blocked / error + date).

## Search terms
Use each platform's search with these terms, 2-4 per platform per day, rotating through the list.
Onboarding fills these in from your field (English and German job titles). Examples for a marketing student:
- Werkstudent Marketing
- Working Student Content
- Praktikum Online-Marketing
- Junior Online Marketing

Locations: Germany (anywhere, remote OK); your home area first (config.yaml search.home). Switzerland only for the Swiss sources.
Posted within: last 7 days (last 1-2 days on high-volume boards if the platform supports it).

## Platforms
Methods in order of preference: API > RSS > FETCH (open the search page with the obscura browser) > SEARCH (web search with site:) > ALERTS (email job alerts).
The order within each row overrides this default.

| On | Platform | Method(s) | Notes | Status |
|----|----------|-----------|-------|--------|
| yes | Arbeitnow | API | https://www.arbeitnow.com/api/job-board-api | |
| yes | Bundesagentur fuer Arbeit | API | rest.arbeitsagentur.de: search via /pc/v6/jobs (v4 search returns 403), details via /pc/v4/jobdetails/<base64 refnr>; header X-API-Key: jobboerse-jobsuche; params was, wo, umkreis, veroeffentlichtseit (filter is loose, so also filter on datumErsteVeroeffentlichung). v6 result list key is `ergebnisliste`, fields stellenangebotsTitel/firma/referenznummer | |
| yes | StepStone | FETCH > ALERTS | https://www.stepstone.de/jobs/<term-with-dashes>?ag=age_7&di=IT (add &fdl=en for English ads). Job links contain /stellenangebote-- | |
| yes | StepStone (student) | FETCH | https://www.stepstone.de/jobs/werkstudent-<term>?ag=age_7&di=IT, same page structure as the StepStone row. Local: /jobs/werkstudent-it/in-<city>?radius=75&ag=age_7 | |
| yes | XING | ALERTS > SEARCH | Obscura can't render XING; use alert emails or web search `site:xing.com/jobs`. Never log in | |
| yes | LinkedIn | ALERTS > SEARCH | Never log in or automate the site. Use alert emails or web search `site:linkedin.com/jobs/view` | |
| yes | Indeed | Connector | Use the Indeed connector (search_jobs + get_job_details). Scraping returns 403. Never store or show the to.indeed.com short links (they expire): resolve each one with `curl -s -o /dev/null -w "%{redirect_url}"`, take the `jk` parameter and write https://de.indeed.com/viewjob?jk=<jk> | |
| yes | SAP Careers | ALERTS > SEARCH | Cloudflare bot check blocks browsing; set up a job alert on jobs.sap.com | |
| yes | EnglishJobs.de | FETCH > SEARCH | English-speaking roles; good fit if your German is basic. Use ?sort=date; extract titles with JS (links are huge) | |
| yes | GermanTechJobs.de | FETCH > SEARCH | Tech-only board (skip it for non-tech fields). Use https://germantechjobs.de/jobs/DevOps/all (also /jobs/System/all); read job links and the ad text with JS. Each ad shows Erfahrungsstufe and Sprache | |
| yes | Company watchlist | API > FETCH | See companies.md | |
| yes | University job board | FETCH > SEARCH | Your university's student-assistant (HiWi) job board; add its URL here | |
| yes | Stellenwerk | FETCH > SEARCH | Student job board run with universities, e.g. https://www.stellenwerk.de/<city>?search=IT | |
| no | jobs.ch (Switzerland) | FETCH > SEARCH | Switch to "yes" when looking at Switzerland | |
| no | Glassdoor | - | Returns 403; keep off | |

## Email job alerts (the most reliable way for StepStone, XING, LinkedIn)
Create saved-search alerts on StepStone, XING and LinkedIn with the terms above, sent daily to your email.
If a mail connector (Gmail/Outlook) is available in this session, read alert emails from the last 24h, open each job link, and treat them like any other result.
With a Gmail connector: Useful senders: jobs@mail.xing.com (search alerts + recommendation digests, the best one), donotreply@match.indeed.com (single matches; look the job up with the Indeed connector by title + company), info@jobagent.stepstone.de, donotreply@jobalert.indeed.com (Switzerland, English). Low value so far: univativ, talent.com, Haystack, eFinancialCareers, Google Careers. XING links can't be opened: find the ad via the Indeed connector, the Arbeitsagentur API or web search. Indeed-Apply emails ("Bewerbung über Indeed: <title>", body "Ihre Bewerbung wurde weitergeleitet") confirm a sent application; the body names no company, so match by title and time with the employer's own confirmation.

## Etiquette (keeps you from getting blocked)
- Max ~10 page fetches per platform per run, a few seconds apart. Never solve CAPTCHAs, log in, or bypass bot protection.
- If a platform blocks you, mark it "blocked <date>" here and move on. After 3 blocked runs in a row, set On = no and mention it in the brief.
