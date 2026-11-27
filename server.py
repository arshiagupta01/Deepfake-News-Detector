from __future__ import annotations

import importlib.util
import os
import re
import threading
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import requests

ROOT = Path(__file__).resolve().parent
GENERATOR_ID = "openai-community/gpt2"
CLASSIFIER_ID = "jy46604790/Fake-News-Bert-Detect"
FACT_CHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

SETTINGS = {
    "cloud-harbor": "Cloud Harbor",
    "mosslight": "Mosslight Valley",
    "bellwether": "Bellwether Bay",
    "starling": "Starling Station",
}
THEME_PREFIXES = {
    "curiosity": ["discover a tiny", "map a new", "find a hidden"],
    "community": ["build a community", "open a tiny", "plant a small"],
    "culture": ["paint a mural", "host a concert", "create an outdoor"],
}
BLOCKED_GENERATION_TERMS = re.compile(
    r"\b(president|election|politician|government|war|attack|bomb|shooting|"
    r"crime|murder|death|dead|deadly|honor|honour|memorial|vaccine|cure|"
    r"disease|outbreak|scandal|crisis|man|woman|boy|girl|child|children|"
    r"person|people|human|hero|heroes|villain|villains|blue-eyed|"
    r"stock|investment|breaking news|real news|missing|lost|loved ones|"
    r"shipmate|honour|mourn|"
    r"future|city|plan|book|real|imaginary|fictional)\b",
    re.IGNORECASE,
)
LOW_QUALITY_GENERATION_PATTERNS = re.compile(
    r"\b(fictional story|do not describe|is not about|there are no words|"
    r"first known town|never again|the future is|it reads|the place where|"
    r"all things are|except for one thing|a real life|in a realistic)\b",
    re.IGNORECASE,
)
INCOMPLETE_ENDING = re.compile(
    r"\b(a|an|the|of|to|for|in|on|with|by|their|its|his|her|my|your|"
    r"favorite|new|old|tiny|life-size|about|from|into|under|over|after|"
    r"before|and|or|but|sometimes|often|especially|hilarious|colorful|"
    r"beautiful|wonderful|interesting|surprising)\s*$",
    re.IGNORECASE,
)
COMMON_SENTENCE_STARTERS = {
    "a", "an", "the", "in", "on", "at", "by", "their", "its", "one",
    "small", "tiny", "local", "new", "old",
}

app = FastAPI(title="Signal / Fiction Lab", docs_url=None, redoc_url=None)


class GenerateRequest(BaseModel):
    setting: Literal["cloud-harbor", "mosslight", "bellwether", "starling"]
    theme: Literal["curiosity", "community", "culture"]


class FactCheckRequest(BaseModel):
    text: str = Field(min_length=8, max_length=240)


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=8, max_length=240)


_generator_lock = threading.Lock()
_classifier_lock = threading.Lock()
_generator = None
_generator_tokenizer = None
_classifier = None
_model_states = {
    "generator": {"loaded": False, "error": None},
    "classifier": {"loaded": False, "error": None},
}


def _load_generator():
    global _generator, _generator_tokenizer
    if _generator is not None:
        return _generator, _generator_tokenizer

    with _generator_lock:
        if _generator is not None:
            return _generator, _generator_tokenizer
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(GENERATOR_ID)
            tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(GENERATOR_ID)
            model.eval()
            _generator_tokenizer = tokenizer
            _generator = model
            _model_states["generator"] = {"loaded": True, "error": None}
        except Exception as exc:
            _model_states["generator"] = {"loaded": False, "error": str(exc)}
            raise

    return _generator, _generator_tokenizer


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier

    with _classifier_lock:
        if _classifier is not None:
            return _classifier
        try:
            from transformers import pipeline

            _classifier = pipeline(
                "text-classification",
                model=CLASSIFIER_ID,
                tokenizer=CLASSIFIER_ID,
                device=-1,
            )
            _model_states["classifier"] = {"loaded": True, "error": None}
        except Exception as exc:
            _model_states["classifier"] = {"loaded": False, "error": str(exc)}
            raise

    return _classifier


def _model_unavailable(stage: str) -> HTTPException:
    state = _model_states[stage]
    dependencies_installed = bool(
        importlib.util.find_spec("torch") and importlib.util.find_spec("transformers")
    )
    detail = (
        "The model could not be loaded. Check your internet connection and model cache."
        if dependencies_installed
        else "Install the dependencies, then restart the app."
    )
    if state["error"]:
        detail = f"{detail} Details: {state['error'][:240]}"
    return HTTPException(status_code=503, detail=detail)


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/styles.css")
def styles():
    return FileResponse(ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def frontend_script():
    return FileResponse(ROOT / "app.js", media_type="text/javascript")


@app.get("/api/status")
def status():
    dependencies_installed = bool(
        importlib.util.find_spec("torch") and importlib.util.find_spec("transformers")
    )
    return {
        "dependencies_installed": dependencies_installed,
        "generator": {
            "id": GENERATOR_ID,
            "loaded": _model_states["generator"]["loaded"],
            "error": bool(_model_states["generator"]["error"]),
        },
        "classifier": {
            "id": CLASSIFIER_ID,
            "loaded": _model_states["classifier"]["loaded"],
            "error": bool(_model_states["classifier"]["error"]),
        },
        "fact_check_search": {
            "provider": "Google Fact Check Explorer",
            "configured": bool(os.getenv("GOOGLE_FACT_CHECK_API_KEY")),
        },
    }


@app.post("/api/generate")
def generate(request: GenerateRequest):
    try:
        import torch

        model, tokenizer = _load_generator()
        setting = SETTINGS[request.setting]
        prefixes = THEME_PREFIXES[request.theme] * 5
        prompts = [
            f"Fictional headline: {setting} residents {prefix}"
            for prefix in prefixes
        ]
        inputs = tokenizer(prompts, return_tensors="pt", padding=True)
        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                do_sample=True,
                max_new_tokens=8,
                num_return_sequences=1,
                no_repeat_ngram_size=3,
                pad_token_id=tokenizer.eos_token_id,
                temperature=0.75,
                top_p=0.88,
            )

        prompt_length = inputs["input_ids"].shape[1]
        headlines = []
        for output, prefix in zip(outputs, prefixes):
            continuation = tokenizer.decode(
                output[prompt_length:], skip_special_tokens=True
            ).strip()
            continuation = re.split(r"[\r\n]", continuation, maxsplit=1)[0]
            continuation = re.split(r"(?<=[.!?])\s", continuation, maxsplit=1)[0]
            continuation = continuation.strip(" \t\r\n:;,.\"'`-")
            continuation = re.sub(r"\s+", " ", continuation)
            words = continuation.split()
            normalized_words = re.findall(
                r"\b[a-z]+\b", f"{prefix} {continuation}".casefold()
            )
            content_words = [
                word
                for word in normalized_words
                if word not in {"a", "an", "the", "of", "to", "for", "in", "on", "with", "and"}
            ]
            has_unexpected_name = any(
                word[0].isupper() and word.casefold() not in COMMON_SENTENCE_STARTERS
                for word in words
                if word and word[0].isalpha()
            )
            if (
                not continuation
                or BLOCKED_GENERATION_TERMS.search(continuation)
                or LOW_QUALITY_GENERATION_PATTERNS.search(continuation)
                or INCOMPLETE_ENDING.search(continuation)
                or re.search(r"[\"'!?]", continuation)
                or has_unexpected_name
                or len(content_words) != len(set(content_words))
            ):
                continue
            if not 2 <= len(words) <= 6:
                continue
            headline = f"{setting} residents {prefix} {continuation}"
            if headline not in headlines:
                headlines.append(headline)
            if len(headlines) == 3:
                break

        if not headlines:
            raise HTTPException(
                status_code=422,
                detail="GPT-2 outputs did not pass the fictional-content filter. Try again.",
            )
        return {
            "headlines": headlines,
            "model": GENERATOR_ID,
            "fictional": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _model_unavailable("generator") from exc


@app.post("/api/classify")
def classify(request: ClassifyRequest):
    try:
        classifier = _load_classifier()
        prediction = classifier(request.text, truncation=True)[0]
    except Exception as exc:
        raise _model_unavailable("classifier") from exc

    model_label = str(prediction["label"])
    normalized_label = model_label.upper().replace(" ", "_")
    if normalized_label in {"LABEL_0", "FAKE", "FAKE_NEWS"}:
        display_label = "Fake news"
    elif normalized_label in {"LABEL_1", "REAL", "REAL_NEWS"}:
        display_label = "Real news"
    else:
        display_label = model_label

    return {
        "label": display_label,
        "score": round(float(prediction["score"]), 4),
        "model": CLASSIFIER_ID,
        "warning": "Experimental signal only. This RoBERTa classifier was trained on full news articles, not headlines. Its raw score is uncalibrated and does not verify truth.",
    }


@app.post("/api/fact-check")
def fact_check(request: FactCheckRequest):
    api_key = os.getenv("GOOGLE_FACT_CHECK_API_KEY")
    if not api_key:
        return {
            "query": request.text,
            "results": [],
            "result_count": 0,
            "fallback": True,
            "search_url": "https://toolbox.google.com/factcheck/explorer/search/" + quote(request.text, safe=""),
            "disclaimer": "No API key is configured, so this app has not queried fact-check reviews. Open the public Explorer search to inspect any related reviews; no result there is not evidence that the claim is true.",
        }

    try:
        response = requests.get(
            FACT_CHECK_API_URL,
            params={
                "query": request.text,
                "languageCode": "en",
                "pageSize": 10,
                "key": api_key,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="The fact-check provider rejected the request. Verify the API key, API access, and quota.",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="The fact-check provider could not be reached. Try again later.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="The fact-check provider returned an unreadable response.",
        ) from exc

    results = []
    seen_urls = set()
    for claim in payload.get("claims", []):
        claim_text = claim.get("text", "")
        for review in claim.get("claimReview", []):
            review_url = review.get("url", "")
            if review_url in seen_urls or urlsplit(review_url).scheme not in {"http", "https"}:
                continue
            seen_urls.add(review_url)
            publisher = review.get("publisher") or {}
            results.append(
                {
                    "claim": claim_text,
                    "claimant": claim.get("claimant", ""),
                    "publisher": publisher.get("name", "Fact-check publisher"),
                    "publisher_site": publisher.get("site", ""),
                    "title": review.get("title", "Fact-check review"),
                    "rating": review.get("textualRating", "Rating not provided"),
                    "review_date": review.get("reviewDate", ""),
                    "url": review_url,
                }
            )
            if len(results) == 10:
                break
        if len(results) == 10:
            break

    return {
        "query": request.text,
        "results": results,
        "result_count": len(results),
        "fallback": False,
        "disclaimer": "These are existing fact-check reviews returned for a related search query. Read the publisher's review and methodology; a matching result is not an automatic verdict, and no results do not mean the claim is true.",
    }