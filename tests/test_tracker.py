"""
Dry-run tests for Claude Token Tracker
No API key required — all Claude calls are mocked.
Run: python -m pytest tests/ -v  OR  python tests/test_tracker.py
"""

import sys
import os
import json
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch DATA_FILE before importing tracker
import tracker as T


class TestTokenCounter(unittest.TestCase):

    def test_count_tokens_empty(self):
        self.assertEqual(T.count_tokens(""), 0)

    def test_count_tokens_approximate(self):
        # 40 chars → ~10 tokens
        text = "a" * 40
        self.assertEqual(T.count_tokens(text), 10)

    def test_count_history_tokens_empty(self):
        self.assertEqual(T.count_history_tokens([]), 0)

    def test_count_history_tokens_multiple(self):
        history = [
            {"role": "user",      "content": "a" * 40},   # 10 tokens
            {"role": "assistant", "content": "b" * 80},   # 20 tokens
        ]
        self.assertEqual(T.count_history_tokens(history), 30)

    def test_count_history_tokens_single(self):
        history = [{"role": "user", "content": "hello"}]
        self.assertEqual(T.count_history_tokens(history), 1)


class TestModelRouter(unittest.TestCase):

    def test_simple_greeting_uses_haiku(self):
        model = T.pick_model("hi")
        self.assertEqual(model, T.MODELS["cheap"])

    def test_short_what_is_uses_haiku(self):
        model = T.pick_model("what is 5G?")
        self.assertEqual(model, T.MODELS["cheap"])

    def test_complex_audit_uses_opus(self):
        model = T.pick_model("perform a full security audit of my infrastructure")
        self.assertEqual(model, T.MODELS["powerful"])

    def test_architecture_uses_opus(self):
        model = T.pick_model("design architecture for my telecom platform")
        self.assertEqual(model, T.MODELS["powerful"])

    def test_normal_task_uses_sonnet(self):
        model = T.pick_model("fix the bug in my Python script")
        self.assertEqual(model, T.MODELS["normal"])

    def test_long_simple_message_uses_sonnet(self):
        # Long message even with simple keyword → Sonnet
        model = T.pick_model("what is " + "a" * 200)
        self.assertEqual(model, T.MODELS["normal"])


class TestCostCalculation(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_file = T.DATA_FILE
        T.DATA_FILE = os.path.join(self.tmp_dir, "test_usage.json")

    def tearDown(self):
        T.DATA_FILE = self.original_file
        shutil.rmtree(self.tmp_dir)

    def test_haiku_cost_calculation(self):
        data = T.load_data()
        cost = T.record_usage(data, T.MODELS["cheap"], 1_000_000, 1_000_000)
        # Haiku: $0.80 in + $4.00 out = $4.80 per 1M each
        self.assertAlmostEqual(cost, 4.80, places=2)

    def test_sonnet_cost_calculation(self):
        data = T.load_data()
        cost = T.record_usage(data, T.MODELS["normal"], 1_000_000, 1_000_000)
        # Sonnet: $3.00 in + $15.00 out = $18.00 per 1M each
        self.assertAlmostEqual(cost, 18.00, places=2)

    def test_opus_cost_calculation(self):
        data = T.load_data()
        cost = T.record_usage(data, T.MODELS["powerful"], 1_000_000, 1_000_000)
        # Opus: $15.00 in + $75.00 out = $90.00 per 1M each
        self.assertAlmostEqual(cost, 90.00, places=2)

    def test_small_usage_cost(self):
        data = T.load_data()
        # 1000 input + 500 output tokens on Haiku
        cost = T.record_usage(data, T.MODELS["cheap"], 1000, 500)
        expected = (1000 / 1_000_000 * 0.80) + (500 / 1_000_000 * 4.00)
        self.assertAlmostEqual(cost, expected, places=8)

    def test_zero_tokens_zero_cost(self):
        data = T.load_data()
        cost = T.record_usage(data, T.MODELS["normal"], 0, 0)
        self.assertEqual(cost, 0.0)


class TestPersistentStorage(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_file = T.DATA_FILE
        T.DATA_FILE = os.path.join(self.tmp_dir, "test_usage.json")

    def tearDown(self):
        T.DATA_FILE = self.original_file
        shutil.rmtree(self.tmp_dir)

    def test_load_data_returns_empty_structure(self):
        data = T.load_data()
        self.assertIn("monthly", data)
        self.assertIn("daily", data)
        self.assertIn("sessions", data)
        self.assertEqual(data["monthly"], {})
        self.assertEqual(data["daily"], {})
        self.assertEqual(data["sessions"], [])

    def test_save_and_reload(self):
        data = T.load_data()
        data["daily"]["2026-04-03"] = {"cost": 1.23, "input_tokens": 500, "output_tokens": 200, "calls": 3}
        T.save_data(data)
        reloaded = T.load_data()
        self.assertAlmostEqual(reloaded["daily"]["2026-04-03"]["cost"], 1.23)
        self.assertEqual(reloaded["daily"]["2026-04-03"]["calls"], 3)

    def test_record_usage_persists_daily(self):
        data = T.load_data()
        T.record_usage(data, T.MODELS["cheap"], 1000, 500)
        reloaded = T.load_data()
        today = str(date.today())
        self.assertIn(today, reloaded["daily"])
        self.assertEqual(reloaded["daily"][today]["calls"], 1)

    def test_record_usage_persists_monthly(self):
        data = T.load_data()
        T.record_usage(data, T.MODELS["normal"], 2000, 1000)
        reloaded = T.load_data()
        this_month = str(date.today())[:7]
        self.assertIn(this_month, reloaded["monthly"])
        self.assertEqual(reloaded["monthly"][this_month]["calls"], 1)

    def test_multiple_calls_accumulate(self):
        data = T.load_data()
        T.record_usage(data, T.MODELS["cheap"], 1000, 500)
        T.record_usage(data, T.MODELS["cheap"], 1000, 500)
        T.record_usage(data, T.MODELS["cheap"], 1000, 500)
        reloaded = T.load_data()
        today = str(date.today())
        self.assertEqual(reloaded["daily"][today]["calls"], 3)
        self.assertEqual(reloaded["daily"][today]["input_tokens"], 3000)

    def test_data_file_created_on_save(self):
        data = T.load_data()
        T.save_data(data)
        self.assertTrue(os.path.exists(T.DATA_FILE))

    def test_json_valid_after_save(self):
        data = T.load_data()
        T.record_usage(data, T.MODELS["normal"], 500, 250)
        with open(T.DATA_FILE) as f:
            parsed = json.load(f)
        self.assertIn("daily", parsed)
        self.assertIn("monthly", parsed)


class TestHistorySummariser(unittest.TestCase):

    def test_short_history_not_compressed(self):
        history = [
            {"role": "user",      "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        mock_client = MagicMock()
        result = T.summarise_history(history, mock_client)
        # < 4 messages → returned as-is, no API call
        self.assertEqual(result, history)
        mock_client.messages.create.assert_not_called()

    def test_long_history_gets_compressed(self):
        history = [
            {"role": "user",      "content": f"message {i}"}
            for i in range(6)
        ] + [
            {"role": "assistant", "content": f"reply {i}"}
            for i in range(6)
        ]
        # Interleave properly
        history = []
        for i in range(6):
            history.append({"role": "user",      "content": f"user message {i} " + "x"*50})
            history.append({"role": "assistant", "content": f"assistant reply {i} " + "x"*50})

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="• Point 1\n• Point 2\n• Point 3")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        result = T.summarise_history(history, mock_client)

        # Should be shorter than original
        self.assertLess(len(result), len(history))
        # First message should be the summary
        self.assertIn("[Previous summary]", result[0]["content"])
        # Last 2 original messages preserved
        self.assertEqual(result[-2], history[-2])
        self.assertEqual(result[-1], history[-1])

    def test_compressed_history_has_summary_prefix(self):
        history = [{"role": "user", "content": f"msg{i}"} for i in range(6)]

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Summary bullet points here")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        result = T.summarise_history(history, mock_client)
        self.assertTrue(result[0]["content"].startswith("[Previous summary]"))


class TestBudgetGuards(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.original_file = T.DATA_FILE
        T.DATA_FILE = os.path.join(self.tmp_dir, "test_usage.json")

    def tearDown(self):
        T.DATA_FILE = self.original_file
        shutil.rmtree(self.tmp_dir)

    def test_budget_not_exceeded_when_empty(self):
        data = T.load_data()
        this_month = str(date.today())[:7]
        monthly_used = data["monthly"].get(this_month, {}).get("cost", 0.0)
        self.assertLess(monthly_used, T.MONTHLY_BUDGET)

    def test_daily_accumulation_correct(self):
        data = T.load_data()
        # Simulate 10 small calls
        for _ in range(10):
            T.record_usage(data, T.MODELS["cheap"], 100, 50)
        today = str(date.today())
        daily_cost = data["daily"][today]["cost"]
        expected = 10 * ((100 / 1_000_000 * 0.80) + (50 / 1_000_000 * 4.00))
        self.assertAlmostEqual(daily_cost, expected, places=8)

    def test_monthly_accumulation_correct(self):
        data = T.load_data()
        for _ in range(5):
            T.record_usage(data, T.MODELS["normal"], 1000, 500)
        this_month = str(date.today())[:7]
        monthly_cost = data["monthly"][this_month]["cost"]
        expected = 5 * ((1000 / 1_000_000 * 3.00) + (500 / 1_000_000 * 15.00))
        self.assertAlmostEqual(monthly_cost, expected, places=8)


class TestModelsConfig(unittest.TestCase):

    def test_all_models_defined(self):
        self.assertIn("cheap",    T.MODELS)
        self.assertIn("normal",   T.MODELS)
        self.assertIn("powerful", T.MODELS)

    def test_all_models_have_costs(self):
        for model_id in T.MODELS.values():
            self.assertIn(model_id, T.COSTS)
            self.assertIn("in",  T.COSTS[model_id])
            self.assertIn("out", T.COSTS[model_id])

    def test_haiku_cheapest(self):
        haiku_in  = T.COSTS[T.MODELS["cheap"]]["in"]
        sonnet_in = T.COSTS[T.MODELS["normal"]]["in"]
        opus_in   = T.COSTS[T.MODELS["powerful"]]["in"]
        self.assertLess(haiku_in, sonnet_in)
        self.assertLess(sonnet_in, opus_in)

    def test_output_more_expensive_than_input(self):
        for model_id, costs in T.COSTS.items():
            self.assertGreater(costs["out"], costs["in"],
                msg=f"{model_id} output should cost more than input")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
