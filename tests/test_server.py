import os
import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException

import server


class FactCheckTests(unittest.TestCase):
    def test_missing_key_returns_prefilled_public_search(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_FACT_CHECK_API_KEY", None)
            result = server.fact_check(
                server.FactCheckRequest(text="sample claim")
            )

        self.assertTrue(result["fallback"])
        self.assertEqual(result["result_count"], 0)
        self.assertTrue(result["search_url"].endswith("/sample%20claim"))
        self.assertIn("not evidence that the claim is true", result["disclaimer"])

    def test_maps_publisher_rating_and_deduplicates_review_url(self):
        response = Mock()
        response.raise_for_status.return_value = None
        review = {
            "publisher": {"name": "Example Fact Check", "site": "example.org"},
            "title": "Review title",
            "textualRating": "Mostly false",
            "reviewDate": "2026-01-01T00:00:00Z",
            "url": "https://example.org/review",
        }
        response.json.return_value = {
            "claims": [
                {
                    "text": "The reviewed claim",
                    "claimant": "Example source",
                    "claimReview": [review, review],
                }
            ]
        }
        with patch.dict(os.environ, {"GOOGLE_FACT_CHECK_API_KEY": "unit-test-key"}):
            with patch.object(server.requests, "get", return_value=response) as get:
                result = server.fact_check(
                    server.FactCheckRequest(text="claim headline")
                )

        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["rating"], "Mostly false")
        self.assertEqual(result["results"][0]["publisher"], "Example Fact Check")
        self.assertEqual(result["results"][0]["url"], "https://example.org/review")
        self.assertEqual(get.call_args.kwargs["params"]["query"], "claim headline")

    def test_empty_provider_results_are_not_a_truth_verdict(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"claims": []}
        with patch.dict(os.environ, {"GOOGLE_FACT_CHECK_API_KEY": "unit-test-key"}):
            with patch.object(server.requests, "get", return_value=response):
                result = server.fact_check(
                    server.FactCheckRequest(text="unreviewed claim")
                )

        self.assertEqual(result["result_count"], 0)
        self.assertFalse(result["fallback"])
        self.assertIn("no results do not mean", result["disclaimer"])

    def test_provider_timeout_is_reported_as_unavailable(self):
        with patch.dict(os.environ, {"GOOGLE_FACT_CHECK_API_KEY": "unit-test-key"}):
            with patch.object(
                server.requests,
                "get",
                side_effect=requests.Timeout("timeout"),
            ):
                with self.assertRaises(HTTPException) as raised:
                    server.fact_check(server.FactCheckRequest(text="claim headline"))

        self.assertEqual(raised.exception.status_code, 502)


class ClassifierTests(unittest.TestCase):
    def test_classifier_returns_model_label_and_limitation_warning(self):
        pipeline = Mock(return_value=[{"label": "LABEL_0", "score": 0.99}])
        with patch.object(server, "_load_classifier", return_value=pipeline):
            result = server.classify(
                server.ClassifyRequest(text="An example headline text")
            )

        self.assertEqual(result["label"], "Fake news")
        self.assertEqual(result["score"], 0.99)
        self.assertIn("uncalibrated", result["warning"])
        self.assertIn("not headlines", result["warning"])
        pipeline.assert_called_once_with("An example headline text", truncation=True)

    def test_classifier_maps_second_label_to_real_news(self):
        pipeline = Mock(return_value=[{"label": "LABEL_1", "score": 0.75}])
        with patch.object(server, "_load_classifier", return_value=pipeline):
            result = server.classify(
                server.ClassifyRequest(text="Another example headline")
            )

        self.assertEqual(result["label"], "Real news")


if __name__ == "__main__":
    unittest.main()