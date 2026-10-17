"""批次单元断言一键运行（设计 §9）。

用法：python docs/batches/tests/run_all.py
脚本内注入仓库根到 sys.path 后跑 unittest。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in ("test_features", "test_persona", "test_card_offline"):
        mod = loader.loadTestsFromName(name)
        suite.addTests(mod)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print()
    print(f"通过 {result.testsRun - len(result.failures) - len(result.errors)}"
          f" / {result.testsRun}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
