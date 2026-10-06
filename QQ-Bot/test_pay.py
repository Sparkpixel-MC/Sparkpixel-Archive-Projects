"""pay.py 单元测试"""
import unittest
from unittest.mock import patch, MagicMock
import pay


class TestParseAtOrName(unittest.TestCase):
    """测试 parse_at_or_name 函数"""

    def test_cq_code_at(self):
        """测试 CQ 码格式的 @"""
        text = "[CQ:at,qq=123456]"
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertEqual(qq_id, "123456")
        self.assertIsNone(player_name)

    def test_cq_code_at_with_extra_text(self):
        """测试 CQ 码后面有额外文本"""
        text = "[CQ:at,qq=123456] some text"
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertEqual(qq_id, "123456")
        self.assertIsNone(player_name)

    def test_direct_name(self):
        """测试直接输入玩家名"""
        text = "Steve"
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertIsNone(qq_id)
        self.assertEqual(player_name, "Steve")

    def test_direct_name_with_spaces(self):
        """测试带空格的玩家名"""
        text = "  Steve  "
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertIsNone(qq_id)
        self.assertEqual(player_name, "Steve")

    def test_empty_string(self):
        """测试空字符串"""
        text = ""
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertIsNone(qq_id)
        self.assertIsNone(player_name)

    def test_whitespace_only(self):
        """测试纯空格"""
        text = "   "
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertIsNone(qq_id)
        self.assertIsNone(player_name)

    def test_other_cq_code(self):
        """测试其他 CQ 码格式"""
        text = "[CQ:image,file=test.jpg]"
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertIsNone(qq_id)
        self.assertIsNone(player_name)

    def test_cq_code_with_large_qq(self):
        """测试大 QQ 号"""
        text = "[CQ:at,qq=99999999999]"
        qq_id, player_name = pay.parse_at_or_name(text)
        self.assertEqual(qq_id, "99999999999")
        self.assertIsNone(player_name)


class TestTransferMoney(unittest.TestCase):
    """测试 transfer_money 函数"""

    @patch("pay.execute_rcon_command")
    def test_transfer_success(self, mock_rcon):
        """测试转账成功"""
        mock_rcon.return_value = "Successfully took 100 from Steve and gave to Alex"
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertTrue(result["success"])
        self.assertIn("转账成功", result["message"])
        mock_rcon.assert_called_once_with("money take Steve 100 Alex")

    @patch("pay.execute_rcon_command")
    def test_transfer_failure_insufficient(self, mock_rcon):
        """测试余额不足"""
        mock_rcon.return_value = "Insufficient funds"
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])
        self.assertIn("Insufficient", result["response"])

    @patch("pay.execute_rcon_command")
    def test_transfer_failure_unknown_player(self, mock_rcon):
        """测试玩家不存在"""
        mock_rcon.return_value = "未知玩家"
        result = pay.transfer_money("Steve", "NotExist", 100)
        self.assertFalse(result["success"])

    @patch("pay.execute_rcon_command")
    def test_transfer_failure_empty_response(self, mock_rcon):
        """测试空响应"""
        mock_rcon.return_value = ""
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "无响应")

    @patch("pay.execute_rcon_command")
    def test_transfer_failure_none_response(self, mock_rcon):
        """测试 None 响应"""
        mock_rcon.return_value = None
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])

    @patch("pay.execute_rcon_command")
    def test_transfer_rcon_exception(self, mock_rcon):
        """测试 RCON 连接异常"""
        mock_rcon.side_effect = ConnectionError("Connection refused")
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])
        self.assertIn("转账执行异常", result["message"])

    @patch("pay.execute_rcon_command")
    def test_transfer_error_keyword_error(self, mock_rcon):
        """测试响应包含 error 关键词"""
        mock_rcon.return_value = "An error occurred"
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])

    @patch("pay.execute_rcon_command")
    def test_transfer_error_keyword_cannot(self, mock_rcon):
        """测试响应包含 cannot 关键词"""
        mock_rcon.return_value = "Cannot take money from this player"
        result = pay.transfer_money("Steve", "Alex", 100)
        self.assertFalse(result["success"])


class TestCheckPlayerExists(unittest.TestCase):
    """测试 check_player_exists 函数"""

    @patch("pay.execute_rcon_command")
    def test_player_exists(self, mock_rcon):
        """测试玩家存在"""
        mock_rcon.return_value = "Steve has 1000 coins"
        result = pay.check_player_exists("Steve")
        self.assertTrue(result)

    @patch("pay.execute_rcon_command")
    def test_player_not_exists_unknown(self, mock_rcon):
        """测试玩家不存在（未知）"""
        mock_rcon.return_value = "未知玩家"
        result = pay.check_player_exists("NotExist")
        self.assertFalse(result)

    @patch("pay.execute_rcon_command")
    def test_player_not_exists_not_found(self, mock_rcon):
        """测试玩家不存在（not found）"""
        mock_rcon.return_value = "Player not found"
        result = pay.check_player_exists("NotExist")
        self.assertFalse(result)

    @patch("pay.execute_rcon_command")
    def test_player_not_exists_empty_response(self, mock_rcon):
        """测试空响应"""
        mock_rcon.return_value = ""
        result = pay.check_player_exists("Steve")
        self.assertFalse(result)

    @patch("pay.execute_rcon_command")
    def test_player_not_exists_none_response(self, mock_rcon):
        """测试 None 响应"""
        mock_rcon.return_value = None
        result = pay.check_player_exists("Steve")
        self.assertFalse(result)

    @patch("pay.execute_rcon_command")
    def test_player_exists_case_insensitive(self, mock_rcon):
        """测试大小写不敏感"""
        mock_rcon.return_value = "STEVE has 1000 coins"
        result = pay.check_player_exists("steve")
        self.assertTrue(result)

    @patch("pay.execute_rcon_command")
    def test_player_not_exists_rcon_exception(self, mock_rcon):
        """测试 RCON 异常"""
        mock_rcon.side_effect = ConnectionError("Connection refused")
        result = pay.check_player_exists("Steve")
        self.assertFalse(result)

    def test_empty_player_name(self):
        """测试空玩家名"""
        result = pay.check_player_exists("")
        self.assertFalse(result)

    def test_none_player_name(self):
        """测试 None 玩家名"""
        result = pay.check_player_exists(None)
        self.assertFalse(result)


class TestExecuteRconCommand(unittest.TestCase):
    """测试 execute_rcon_command 函数"""

    def test_execute_success(self):
        """测试执行成功"""
        mock_mcr = MagicMock()
        mock_mcr.command.return_value = "Success"
        mock_mcrcon_class = MagicMock()
        mock_mcrcon_class.return_value.__enter__ = MagicMock(return_value=mock_mcr)
        mock_mcrcon_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict('sys.modules', {'mcrcon': MagicMock(MCRcon=mock_mcrcon_class)}):
            result = pay.execute_rcon_command("money Steve")
            self.assertEqual(result, "Success")

    def test_execute_connection_error(self):
        """测试连接错误"""
        mock_mcrcon_class = MagicMock(side_effect=ConnectionError("Connection refused"))

        with patch.dict('sys.modules', {'mcrcon': MagicMock(MCRcon=mock_mcrcon_class)}):
            with self.assertRaises(ConnectionError):
                pay.execute_rcon_command("money Steve")


if __name__ == "__main__":
    unittest.main()
