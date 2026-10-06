"""get_qqid.py 单元测试"""
import unittest
from unittest.mock import patch, MagicMock
import sqlite3
import get_qqid


class TestGetEid(unittest.TestCase):
    """测试 get_eid 函数"""

    @patch("get_qqid.sqlite3.connect")
    def test_get_eid_found(self, mock_connect):
        """测试成功获取 eid"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        result = get_qqid.get_eid("123456")
        self.assertEqual(result, 42)
        mock_cursor.execute.assert_called_once_with(
            'SELECT id FROM SocialAccount WHERE Uuid = ?', ("123456",)
        )
        mock_conn.close.assert_called_once()

    @patch("get_qqid.sqlite3.connect")
    def test_get_eid_not_found(self, mock_connect):
        """测试 eid 不存在"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = get_qqid.get_eid("999999")
        self.assertIsNone(result)
        mock_conn.close.assert_called_once()

    @patch("get_qqid.sqlite3.connect")
    def test_get_eid_db_error(self, mock_connect):
        """测试数据库错误"""
        mock_connect.side_effect = sqlite3.Error("DB error")

        result = get_qqid.get_eid("123456")
        self.assertIsNone(result)

    @patch("get_qqid.sqlite3.connect")
    def test_get_eid_connection_closed_on_error(self, mock_connect):
        """测试异常时连接被关闭"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = sqlite3.Error("Query error")

        result = get_qqid.get_eid("123456")
        self.assertIsNone(result)
        mock_conn.close.assert_called_once()


class TestGetGamenick(unittest.TestCase):
    """测试 get_gamenick 函数"""

    @patch("get_qqid.get_eid")
    @patch("get_qqid.sqlite3.connect")
    def test_get_gamenick_found(self, mock_connect, mock_get_eid):
        """测试成功获取游戏昵称"""
        mock_get_eid.return_value = 42
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("Steve",)

        result = get_qqid.get_gamenick("123456")
        self.assertEqual(result, "Steve")
        mock_get_eid.assert_called_once_with("123456")
        mock_cursor.execute.assert_called_once_with(
            'SELECT Name FROM Player WHERE SocialAccountId = ?', (42,)
        )
        mock_conn.close.assert_called_once()

    @patch("get_qqid.get_eid")
    def test_get_gamenick_no_eid(self, mock_get_eid):
        """测试 eid 不存在"""
        mock_get_eid.return_value = None

        result = get_qqid.get_gamenick("999999")
        self.assertIsNone(result)

    @patch("get_qqid.get_eid")
    @patch("get_qqid.sqlite3.connect")
    def test_get_gamenick_no_player(self, mock_connect, mock_get_eid):
        """测试玩家不存在"""
        mock_get_eid.return_value = 42
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = get_qqid.get_gamenick("123456")
        self.assertIsNone(result)
        mock_conn.close.assert_called_once()

    @patch("get_qqid.get_eid")
    @patch("get_qqid.sqlite3.connect")
    def test_get_gamenick_db_error(self, mock_connect, mock_get_eid):
        """测试数据库错误"""
        mock_get_eid.return_value = 42
        mock_connect.side_effect = sqlite3.Error("DB error")

        result = get_qqid.get_gamenick("123456")
        self.assertIsNone(result)

    @patch("get_qqid.get_eid")
    @patch("get_qqid.sqlite3.connect")
    def test_get_gamenick_connection_closed_on_error(self, mock_connect, mock_get_eid):
        """测试异常时连接被关闭"""
        mock_get_eid.return_value = 42
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = sqlite3.Error("Query error")

        result = get_qqid.get_gamenick("123456")
        self.assertIsNone(result)
        mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
