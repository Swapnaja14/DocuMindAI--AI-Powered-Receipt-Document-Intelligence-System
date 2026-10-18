import json
from pathlib import Path
from typing import List

from evaluation.documents import EVALUATION_DOCUMENTS
from evaluation.schema import EvaluationBenchmark, EvaluationItem


def load_dev_benchmark() -> EvaluationBenchmark:
    benchmark_file = Path(__file__).parent / "dev_benchmark.json"
    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvaluationBenchmark.model_validate(data)


def load_holdout_benchmark() -> EvaluationBenchmark:
    benchmark_file = Path(__file__).parent / "holdout_benchmark.json"
    with open(benchmark_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EvaluationBenchmark.model_validate(data)


def get_all_evaluation_documents() -> list:
    return EVALUATION_DOCUMENTS
