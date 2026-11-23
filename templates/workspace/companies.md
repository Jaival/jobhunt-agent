# Company watchlist: career pages checked directly

Add companies you want to watch. Leave ATS / Endpoint empty: on the next run the ad reader finds the careers
page and the applicant-tracking system, and `engine/tools/extract.py` saves the endpoint here (Personio, Ashby,
Greenhouse and Lever; other systems stay a careers page the reader checks). An endpoint you found yourself:
`python engine/tools/extract.py endpoint "<Company>" <url>`.

Known public job endpoints, preferred over scraping:
- Greenhouse:      https://boards-api.greenhouse.io/v1/boards/<board>/jobs?content=true
- Lever:           https://api.lever.co/v0/postings/<company>?mode=json
- Ashby:           https://api.ashbyhq.com/posting-api/job-board/<board>
- Personio:        https://<company>.jobs.personio.de/xml  (or .personio.com)
- SmartRecruiters: https://api.smartrecruiters.com/v1/companies/<id>/postings?q=<term>
- Workday:         POST https://<tenant>.wd<N>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs  body {"searchText":"DevOps","limit":20,"offset":0}
- SuccessFactors / own site: fetch the search page with the term

| Company | Careers page | ATS | Endpoint | Last checked |
|---------|--------------|-----|----------|--------------|
| DeepL | jobs.ashbyhq.com/deepl | Ashby | https://api.ashbyhq.com/posting-api/job-board/deepl | |
| Statista | jobs.ashbyhq.com/statista | Ashby | https://api.ashbyhq.com/posting-api/job-board/statista | |
| Example GmbH | | | | |
