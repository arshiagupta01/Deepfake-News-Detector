# Signal / Fiction Lab

A local educational app demonstrating GPT-2 fictional headline generation, an experimental BERT-family text classifier, and source-backed fact-check lookup. It distinguishes model predictions from publisher-reviewed evidence rather than presenting either as an automatic truth verdict.

## Run locally

Use Python 3.10 or newer. From the project directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload
```

No key is required to use the public-search fallback. Without a key, the app opens a prefilled Google Fact Check Explorer search in a new tab; it does not fetch or summarize those results inside the app.

For in-app results, optionally enable the Google Fact Check Tools API in a Google Cloud project, create an API key, and set it in the same PowerShell session before starting the server:

```powershell
$env:GOOGLE_FACT_CHECK_API_KEY = "YOUR_API_KEY"
```

Restrict the key to the Fact Check Tools API. Do not commit the key. Then run the server and open <http://127.0.0.1:8000>. GPT-2 and RoBERTa weights download from Hugging Face on their first use (roughly 550 MB and 500 MB respectively). Model downloads and both lookup modes require internet access.

## Validate

Run the offline unit tests from the project directory:

```powershell
python -m unittest discover -s tests -v
```

## Models

- Generation: `openai-community/gpt2`, loaded locally through Transformers. The UI offers only preset themes and imaginary settings; it does not accept a free-form generation prompt. Generated text is labeled fictional and screened for a small set of sensitive topics. This filter is a safeguard, not a guarantee.
- Classification: `jy46604790/Fake-News-Bert-Detect`, a RoBERTa (BERT-family) classifier. It was trained on full news articles, not headlines. Its output is a secondary experimental signal; its confidence score is uncalibrated and can be confidently wrong.
- Evidence lookup: Google's Fact Check Tools `claims.search` endpoint, which searches claims indexed by Fact Check Explorer. The app displays publisher, their textual rating, review date, and a link to the original review. Ratings are not normalized across publishers, and search results can be related rather than exact matches.

## Limitations

This is an educational prototype, not an automatic truth detector. A matching review is a source to inspect, not a verdict from this app; no results mean no matching review was found, not that a claim is true. Fact-check coverage is incomplete. The RoBERTa model was not fine-tuned or evaluated on a headline-specific benchmark in this project. In a live smoke test, it labeled a clearly fictional headline "Fake news" with a 100% raw score; this is a known false positive, not an accuracy metric. Read cited reviews and confirm important claims with multiple reliable, independent sources.

Model references: [GPT-2](https://huggingface.co/openai-community/gpt2), [RoBERTa fake-news classifier](https://huggingface.co/jy46604790/Fake-News-Bert-Detect), and [Google Fact Check Tools API](https://developers.google.com/fact-check/tools/api).