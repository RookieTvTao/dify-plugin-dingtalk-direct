import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _utils.dingtalk_client import (  # noqa: E402
    build_robot_msg,
    build_work_msg,
    check_content_size,
    match_department_by_name,
    matches_user,
    split_ids,
)


class SplitIdsTest(unittest.TestCase):
    def test_splits_and_trims(self):
        self.assertEqual(split_ids(" a, b ,,c "), ["a", "b", "c"])

    def test_empty(self):
        self.assertEqual(split_ids(""), [])
        self.assertEqual(split_ids(None), [])  # type: ignore[arg-type]


class WorkMsgTest(unittest.TestCase):
    def test_text(self):
        msg = build_work_msg("text", "", "hello")
        self.assertEqual(msg, {"msgtype": "text", "text": {"content": "hello"}})

    def test_markdown_defaults_title_from_first_line(self):
        msg = build_work_msg("markdown", "", "# 晨报\n正文")
        self.assertEqual(msg["msgtype"], "markdown")
        self.assertEqual(msg["markdown"]["title"], "晨报")
        self.assertEqual(msg["markdown"]["text"], "# 晨报\n正文")

    def test_markdown_explicit_title_wins(self):
        msg = build_work_msg("markdown", "自定义标题", "# 晨报\n正文")
        self.assertEqual(msg["markdown"]["title"], "自定义标题")


class RobotMsgTest(unittest.TestCase):
    def test_text(self):
        key, param = build_robot_msg("text", "", "hi 你好")
        self.assertEqual(key, "sampleText")
        self.assertEqual(json.loads(param), {"content": "hi 你好"})

    def test_markdown(self):
        key, param = build_robot_msg("markdown", "T", "# h\nbody")
        self.assertEqual(key, "sampleMarkdown")
        self.assertEqual(json.loads(param), {"title": "T", "text": "# h\nbody"})


class ContentSizeTest(unittest.TestCase):
    def test_over_limit_raises(self):
        with self.assertRaises(Exception):
            check_content_size("字" * 1025)  # 1025 * 3 bytes > 2048

    def test_under_limit_ok(self):
        check_content_size("字" * 100)


class ToBoolTest(unittest.TestCase):
    def test_string_bools(self):
        from _utils.dingtalk_client import to_bool

        self.assertTrue(to_bool(True))
        self.assertTrue(to_bool("True"))
        self.assertTrue(to_bool("true"))
        self.assertTrue(to_bool("1"))
        self.assertFalse(to_bool(False))
        self.assertFalse(to_bool("False"))
        self.assertFalse(to_bool("0"))
        self.assertFalse(to_bool(None))
        self.assertFalse(to_bool(""))


class MatchesUserTest(unittest.TestCase):
    def test_empty_keyword_matches_all(self):
        self.assertTrue(matches_user({"name": "张三"}, ""))
        self.assertTrue(matches_user({}, ""))

    def test_name_substring(self):
        self.assertTrue(matches_user({"name": "王小陶"}, "小陶"))
        self.assertFalse(matches_user({"name": "王小陶"}, "小陶1"))

    def test_job_number_exact(self):
        self.assertTrue(matches_user({"name": "x", "job_number": "1000010002"}, "1000010002"))
        self.assertFalse(matches_user({"name": "x", "job_number": "1000010002"}, "100001000"))
        self.assertFalse(matches_user({"name": "x"}, "1000010002"))

    def test_job_number_numeric_type(self):
        self.assertTrue(matches_user({"job_number": 1000010002}, "1000010002"))


class MatchDepartmentTest(unittest.TestCase):
    CHILDREN = [
        {"dept_id": 1, "name": "示例集团股份有限公司"},
        {"dept_id": 2, "name": "示例集团（华东）有限公司"},
        {"dept_id": 3, "name": "示例食品（集团）有限公司"},
    ]

    def test_exact_unique(self):
        dept_id, cands = match_department_by_name(self.CHILDREN, "示例集团股份有限公司")
        self.assertEqual((dept_id, cands), (1, []))

    def test_substring_unique(self):
        dept_id, cands = match_department_by_name(self.CHILDREN, "食品")
        self.assertEqual((dept_id, cands), (3, []))

    def test_ambiguous_returns_candidates(self):
        dept_id, cands = match_department_by_name(self.CHILDREN, "示例集团")
        self.assertIsNone(dept_id)
        self.assertEqual(len(cands), 2)

    def test_no_match(self):
        dept_id, cands = match_department_by_name(self.CHILDREN, "不存在的部门")
        self.assertIsNone(dept_id)
        self.assertEqual(cands, [])


if __name__ == "__main__":
    unittest.main()
